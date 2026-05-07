"""
UBID Platform — Activity Intelligence Service (Production)

Hybrid classification engine:
  RULE LAYER: Time-decayed signal scoring (deterministic)
  LLM LAYER: Natural language explanation (llama3.1:8b)

Activity signals come from government department event streams:
  - Positive: renewals, inspections, compliance filings, utility usage
  - Negative: disconnections, closure declarations, long inactivity
"""

import math
import logging
from datetime import date, datetime
from typing import Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger("ubid.activity")


# ── Status Thresholds ────────────────────────────────────────────────────────

ACTIVE_THRESHOLD = 1.5   # sum of decayed signals ≥ 1.5 → Active
DORMANT_THRESHOLD = 0.0  # between 0 and 1.5 → Dormant
# below 0 (net negative signals) → Closed


# ── Data Types ───────────────────────────────────────────────────────────────

@dataclass
class EvidenceEntry:
    event_id: str
    event_type: str
    event_date: str
    source_system: str
    signal_strength: str
    raw_weight: float
    days_old: int
    decay_weight: float


@dataclass
class ClassificationResult:
    status: str         # Active | Dormant | Closed
    score: float
    evidence_timeline: list
    computed_at: str


# ── Decay Function ───────────────────────────────────────────────────────────

def _decayed_weight(raw_weight: float, decay_days: int, days_old: int) -> float:
    """
    Exponential decay: weight * exp(-ln(2) * days_old / half_life)
    Half-life = decay_days parameter from signal_taxonomy.
    """
    if decay_days <= 0:
        return raw_weight
    lam = math.log(2) / decay_days
    return raw_weight * math.exp(-lam * days_old)


# ── Rule-Based Classifier ────────────────────────────────────────────────────

def classify_ubid(
    events: list[dict],
    signal_taxonomy: dict[str, dict],
    reference_date: Optional[date] = None,
    existing_override: Optional[str] = None,
) -> ClassificationResult:
    """
    Classify a UBID's activity status using time-decayed signals.

    This is the RULE LAYER. The LLM LAYER (explanation) is called separately
    via llm_service.explain_activity().

    Args:
        events: List of event dicts with keys:
                  id, event_type, event_date (date), source_system, payload
        signal_taxonomy: dict keyed by event_type, each entry:
                  {signal_strength, decay_days, weight, is_active}
        reference_date: date to compute age against (default: today)
        existing_override: if set, preserves the override verdict

    Returns:
        ClassificationResult
    """
    ref = reference_date or date.today()
    evidence_timeline = []
    total_score = 0.0

    for event in events:
        etype = event.get("event_type", "").lower()
        sig = signal_taxonomy.get(etype)

        if not sig or not sig.get("is_active", True):
            continue

        # Compute age
        ev_date = event.get("event_date")
        if isinstance(ev_date, str):
            try:
                ev_date = date.fromisoformat(ev_date)
            except ValueError:
                continue
        if isinstance(ev_date, datetime):
            ev_date = ev_date.date()

        days_old = max(0, (ref - ev_date).days)
        raw_weight = sig["weight"]
        decay_w = _decayed_weight(raw_weight, sig["decay_days"], days_old)
        total_score += decay_w

        evidence_timeline.append(EvidenceEntry(
            event_id=str(event.get("id", "")),
            event_type=etype,
            event_date=ev_date.isoformat(),
            source_system=event.get("source_system", "unknown"),
            signal_strength=sig["signal_strength"],
            raw_weight=round(raw_weight, 3),
            days_old=days_old,
            decay_weight=round(decay_w, 4),
        ))

    # Sort timeline chronologically (newest first)
    evidence_timeline.sort(key=lambda e: e.event_date, reverse=True)

    # Determine status
    if existing_override:
        status = existing_override
    elif total_score >= ACTIVE_THRESHOLD:
        status = "Active"
    elif total_score >= DORMANT_THRESHOLD:
        status = "Dormant"
    else:
        status = "Closed"

    return ClassificationResult(
        status=status,
        score=round(total_score, 4),
        evidence_timeline=[asdict(e) for e in evidence_timeline],
        computed_at=datetime.utcnow().isoformat(),
    )
