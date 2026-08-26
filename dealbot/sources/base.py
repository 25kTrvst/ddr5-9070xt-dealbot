from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Candidate, Kind


class SourceError(RuntimeError):
    pass


class BlockedSource(SourceError):
    pass


class Source(ABC):
    name: str

    @abstractmethod
    async def search(self, kind: Kind) -> list[Candidate]: ...


class QueryRotation:
    """Checking every configured speed/capacity/model query on every single
    scan cycle multiplies request volume by however many combos are
    configured - against eBay that risks blowing through the daily API
    quota, and against scraped stores it multiplies block risk. Instead,
    rotate through the set one at a time: each cycle checks one combo, and
    the full set gets covered over successive cycles rather than every one."""

    def __init__(self) -> None:
        self._index = 0

    def next(self, queries: tuple[str, ...]) -> tuple[str, ...]:
        if len(queries) <= 1:
            return queries
        query = queries[self._index % len(queries)]
        self._index += 1
        return (query,)


def money(value: object) -> float | None:
    try:
        if isinstance(value, dict):
            value = value.get("value")
        return round(float(str(value).replace("$", "").replace(",", "").strip()), 2)
    except (TypeError, ValueError):
        return None
