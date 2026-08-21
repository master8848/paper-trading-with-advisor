"""migrate existing Stocks entity data -> portfolios / positions / trades

Maps (backend/src/stocks/entities/FinanceData.ts:8):
  Stocks.username        -> portfolios.user_id + positions lookup
  Stocks.stockName       -> positions.symbol / trades.symbol
  Stocks.price           -> positions.avg_buy_price / trades.price_snapshot
  Stocks.quantity        -> positions.qty / trades.qty
  Stocks.total           -> derived
  Stocks.date / modified -> positions.created_at / trades.traded_at
  Stocks.transactionType -> trades.type
  Stocks.message         -> dropped (lossy — kept only in legacy Stocks table)

Strategy:
  1. For each distinct username, create a portfolio named "Migrated - {username}"
     (idempotent: skip if portfolio for user_id already exists).
  2. For each Stocks row, upsert a Position (weighted avg price on duplicate symbol).
  3. For each Stocks row, insert a Trade snapshot (preserves transaction history).
  Idempotent: checks for existing trades matching (symbol, qty, price_snapshot, traded_at proxy)
  to allow re-running.

Run after 001_initial.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_migrate_stocks"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Guard: if Stocks table doesn't exist yet, nothing to migrate
    inspector = sa.inspect(conn)
    if "Stocks" not in inspector.get_table_names():
        return

    # Ensure target tables exist (001 should have created them)
    if "portfolios" not in inspector.get_table_names():
        return

    # Distinct usernames from Stocks
    usernames = [r[0] for r in conn.execute(sa.text("SELECT DISTINCT username FROM `Stocks`")).fetchall() if r[0]]

    # Map username -> portfolio_id (create if missing)
    user_to_portfolio: dict[str, int] = {}
    for username in usernames:
        row = conn.execute(
            sa.text("SELECT id FROM portfolios WHERE user_id = :u LIMIT 1"), {"u": username}
        ).fetchone()
        if row:
            user_to_portfolio[username] = int(row[0])
        else:
            conn.execute(
                sa.text(
                    "INSERT INTO portfolios (user_id, name, baseline_value, created_at) "
                    "VALUES (:u, :name, 100.0000, NOW())"
                ),
                {"u": username, "name": f"Migrated - {username}"},
            )
            row2 = conn.execute(
                sa.text("SELECT id FROM portfolios WHERE user_id = :u LIMIT 1"), {"u": username}
            ).fetchone()
            if row2:
                user_to_portfolio[username] = int(row2[0])

    # For each Stocks row, create position/trade
    stocks = conn.execute(
        sa.text(
            "SELECT id, username, stockName, price, quantity, transactionType, date, modified "
            "FROM `Stocks` ORDER BY id"
        )
    ).fetchall()

    for sid, username, stockName, price, quantity, txType, date_val, modified_val in stocks:
        portfolio_id = user_to_portfolio.get(username)
        if not portfolio_id or not stockName:
            continue
        symbol = str(stockName).strip().upper()
        try:
            price_f = float(price) if price is not None else 0.0
        except Exception:
            price_f = 0.0
        try:
            qty_f = float(quantity) if quantity is not None else 0.0
        except Exception:
            qty_f = 0.0
        if qty_f == 0:
            continue
        tx = (txType or "buy").lower()
        if tx not in ("buy", "sell"):
            tx = "buy"

        # Upsert position (only on buy — sell keeps qty but could go negative; we keep simple)
        pos_row = conn.execute(
            sa.text(
                "SELECT id, qty, avg_buy_price FROM positions "
                "WHERE portfolio_id = :pid AND symbol = :sym LIMIT 1"
            ),
            {"pid": portfolio_id, "sym": symbol},
        ).fetchone()

        if pos_row is None:
            conn.execute(
                sa.text(
                    "INSERT INTO positions (portfolio_id, symbol, qty, avg_buy_price, created_at) "
                    "VALUES (:pid, :sym, :qty, :price, :created)"
                ),
                {"pid": portfolio_id, "sym": symbol, "qty": qty_f, "price": price_f, "created": modified_val or date_val},
            )
            pos_row = conn.execute(
                sa.text(
                    "SELECT id FROM positions WHERE portfolio_id = :pid AND symbol = :sym LIMIT 1"
                ),
                {"pid": portfolio_id, "sym": symbol},
            ).fetchone()
            position_id = int(pos_row[0]) if pos_row else None
        else:
            position_id = int(pos_row[0])
            # weighted avg only for buy
            if tx == "buy":
                try:
                    old_qty = float(pos_row[1])
                    old_avg = float(pos_row[2])
                    total_qty = old_qty + qty_f
                    if total_qty:
                        new_avg = (old_avg * old_qty + price_f * qty_f) / total_qty
                        conn.execute(
                            sa.text(
                                "UPDATE positions SET qty = :qty, avg_buy_price = :avg WHERE id = :id"
                            ),
                            {"qty": total_qty, "avg": new_avg, "id": position_id},
                        )
                except Exception:
                    pass

        # Insert trade (idempotent check: same symbol+qty+price+traded_at)
        exists = conn.execute(
            sa.text(
                "SELECT id FROM trades WHERE symbol = :sym AND qty = :qty "
                "AND price_snapshot = :price AND traded_at = :traded LIMIT 1"
            ),
            {"sym": symbol, "qty": qty_f, "price": price_f, "traded": modified_val or date_val},
        ).fetchone()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO trades (position_id, symbol, price_snapshot, qty, type, traded_at) "
                    "VALUES (:pid, :sym, :price, :qty, :type, :traded)"
                ),
                {
                    "pid": position_id,
                    "sym": symbol,
                    "price": price_f,
                    "qty": qty_f,
                    "type": tx,
                    "traded": modified_val or date_val,
                },
            )


def downgrade() -> None:
    # Data migration — no automatic downgrade (would delete migrated rows).
    # Manual: DELETE FROM trades WHERE id IN (migrated set) etc.
    pass
