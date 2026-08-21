"""
Duration filter logic — Python port of backend/src/stocks/stocks.service.ts:29

Original (moment.js):
  tweek  -> MoreThan(moment().startOf('week'))
  lweek  -> Between(moment().subtract(1,'week').startOf('week'), moment().startOf('week'))
  tmonth -> MoreThan(moment().startOf('month'))
  lmonth -> Between(moment().subtract(1,'month').startOf('month'), moment().startOf('month'))
  tyear  -> MoreThan(moment().startOf('year'))
  lyear  -> Between(moment().subtract(1,'year').startOf('year'), moment().startOf('year'))
  default -> no filter

moment.startOf semantics (en locale):
  week  = Sunday 00:00:00
  month = 1st 00:00:00
  year  = Jan 1 00:00:00

Python uses dateutil.relativedelta for month/year arithmetic and plain
datetime for week (no external pendulum required, but pendulum is optional).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Tuple

from dateutil.relativedelta import relativedelta


def _start_of_week(dt: datetime) -> datetime:
    """Sunday 00:00:00 — matches moment().startOf('week') in en locale."""
    # weekday(): Mon=0 .. Sun=6; Sunday offset = (weekday+1)%7 days back
    days_since_sunday = (dt.weekday() + 1) % 7
    sunday = dt - timedelta(days=days_since_sunday)
    return sunday.replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_month(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _start_of_year(dt: datetime) -> datetime:
    return dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def duration_bounds(
    duration: Optional[str],
    now: Optional[datetime] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Returns (start, end) bounds for SQL filtering.
    If end is None -> open-ended MoreThan(start).
    If both set   -> Between(start, end).
    If both None  -> no filter (default).
    Caller applies as:
      if start and end:   WHERE modified BETWEEN start AND end
      elif start:         WHERE modified > start
      else:               no filter
    """
    if now is None:
        now = datetime.now()

    key = (duration or "").strip().lower()

    if key == "tweek":
        return _start_of_week(now), None
    if key == "lweek":
        this_sunday = _start_of_week(now)
        last_sunday = _start_of_week(now - timedelta(weeks=1))
        return last_sunday, this_sunday
    if key == "tmonth":
        return _start_of_month(now), None
    if key == "lmonth":
        this_first = _start_of_month(now)
        last_first = this_first - relativedelta(months=1)
        return last_first, this_first
    if key == "tyear":
        return _start_of_year(now), None
    if key == "lyear":
        this_jan1 = _start_of_year(now)
        last_jan1 = this_jan1 - relativedelta(years=1)
        return last_jan1, this_jan1
    # default: all rows
    return None, None
