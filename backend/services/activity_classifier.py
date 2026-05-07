"""
UBID Platform — Activity Classifier (Module 11)

Classifies each UBID as Active / Dormant / Closed using
time-decayed signals from the event stream.

Design principles:
- All parameters come from signal_taxonomy table (configurable, not hardcoded)
- Decay is exponential: weight * exp(-lambda * days_old)
- Evidence timeline is serialised for every verdict
- Reviewer overrides persist across re-classification
"""

import math
from datetime import date, datetime
from typing import Optional
from dataclasses import dataclass, field, asdict


# ── Status thresholds ─────────────────────────────────────────────────────────
# These can be moved to a config table if needed.
ACTIVE_THRESHOLD  = 1.5   # sum of decayed signals >= 1.5 → Active
DORMANT_THRESHOLD = 0.0   # between 0 and 1.5 → Dormant
# below 0 (net negative signals) → Closed


@dataclass
class EvidenceEntry:
    event_id:     str
    event_type:   str
    event_date:   str          # ISO date string
    source_system: str
    signal_strength: str
    raw_weight:   float
    days_old:     int
    decay_weight: float        # after exponential decay


@dataclass
class ClassificationResult:
    status:            str     # Active | Dormant | Closed
    score:             float
    evidence_timeline: list    # List[EvidenceEntry as dict]
    computed_at:       str


# ── Decay function ────────────────────────────────────────────────────────────

def _decayed_weight(raw_weight: float, decay_days: int, days_old: int) -> float:
    """
    Exponential decay: weight * exp(-ln(2) * days_old / half_life)
    Half-life = decay_days parameter from signal_taxonomy.
    """
    if decay_days <= 0:
        return raw_weight
    lam = math.log(2) / decay_days
    return raw_weight * math.exp(-lam * days_old)


# ── Main classifier ───────────────────────────────────────────────────────────

def classify_ubid(
    events: list[dict],
    signal_taxonomy: dict[str, dict],
    reference_date: Optional[date] = None,
    existing_override: Optional[str] = None,
) -> ClassificationResult:
    """
    Classify a UBID's activity status.

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
    if existing_override:
        # Respect reviewer override — recompute evidence but preserve verdict
        pass  # fall through to compute evidence, then override verdict at end

    ref = reference_date or date.today()
    evidence_timeline = []
    total_score = 0.0

    for event in events:
        etype = event.get("event_type", "").lower()
        sig   = signal_taxonomy.get(etype)

        if not sig or not sig.get("is_active", True):
            continue  # unknown or disabled event type

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
        decay_w    = _decayed_weight(raw_weight, sig["decay_days"], days_old)
        total_score += decay_w

        evidence_timeline.append(EvidenceEntry(
            event_id      = str(event.get("id", "")),
            event_type    = etype,
            event_date    = ev_date.isoformat(),
            source_system = event.get("source_system", "unknown"),
            signal_strength = sig["signal_strength"],
            raw_weight    = round(raw_weight, 3),
            days_old      = days_old,
            decay_weight  = round(decay_w, 4),
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
        status            = status,
        score             = round(total_score, 4),
        evidence_timeline = [asdict(e) for e in evidence_timeline],
        computed_at       = datetime.utcnow().isoformat(),
    )
