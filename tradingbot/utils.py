from __future__ import annotations


def pct_change(previous: float, current: float) -> float:
    """Percent change from previous to current. previous must be non-zero."""
    return (current - previous) / previous * 100
