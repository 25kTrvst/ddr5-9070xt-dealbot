from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

Kind = Literal["ram", "gpu"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Candidate:
    source: str
    source_id: str
    kind: Kind
    title: str
    url: str
    price: float
    currency: str = "USD"
    shipping: float | None = None
    condition: str = "unknown"
    stock: str = "unknown"
    category_id: str = ""
    category_name: str = ""
    aspects: dict[str, list[str]] = field(default_factory=dict)
    seller_feedback_score: int | None = None
    seller_feedback_percent: float | None = None
    source_confidence: int = 50
    discovered_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def checkout_known(self) -> float:
        return round(self.price + (self.shipping or 0.0), 2)


@dataclass(slots=True)
class Classification:
    accepted: bool
    confidence: int
    reasons: list[str]
    model_key: str = ""
    speed_mts: int | None = None
    cas_latency: int | None = None
    kit_config: str = ""
    capacity_gb: int | None = None
    identity_label: str = ""


@dataclass(slots=True)
class Deal:
    candidate: Candidate
    classification: Classification
    score: int
    recommendation: str
    recommendation_reason: str
    tax: float
    estimated_total: float
    history_observations: int = 0
    previous_price: float | None = None
    low_30d: float | None = None
    alert_reason: str = "new listing"
    market_baseline: float | None = None
    low_30d_all_sources: float | None = None
    market_sample_count: int = 0
    unconfirmed: bool = False
    restocked: bool = False

    @property
    def kind(self) -> Kind:
        return self.candidate.kind

