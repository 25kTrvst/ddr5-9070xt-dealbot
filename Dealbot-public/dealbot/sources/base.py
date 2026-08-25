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


def money(value: object) -> float | None:
    try:
        if isinstance(value, dict):
            value = value.get("value")
        return round(float(str(value).replace("$", "").replace(",", "").strip()), 2)
    except (TypeError, ValueError):
        return None
