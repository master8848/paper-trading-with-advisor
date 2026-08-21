"""Shared enums."""

from __future__ import annotations

import enum


class TransactionType(str, enum.Enum):
    buy = "buy"
    sell = "sell"
