"""UBID Platform — Decision Engine (Module 5)"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DecisionResult:
    decision_type: str      # auto_link | review_queue | separate
    threshold_version: str
    confidence_score: float
    reason: str


def make_decision(
    confidence_score: float,
    threshold_config: dict,
    evidence_object: Optional[dict] = None,
) -> DecisionResult:
    """
    Route a scored pair to auto_link, review_queue, or separate
    based on the active threshold config.

    Hard safety rules applied before threshold check:
    - Conflicting PAN → force separate (never auto-link conflicting anchors)
    - Conflicting GSTIN → force separate
    """
    version = threshold_config.get("version", "v1.0")
    auto_min  = threshold_config.get("auto_link_min", 0.92)
    review_min = threshold_config.get("review_min", 0.75)

    # Hard safety: conflicting identifiers
    if evidence_object:
        if evidence_object.get("conflicting_pan") or evidence_object.get("conflicting_gstin"):
            return DecisionResult(
                decision_type="separate",
                threshold_version=version,
                confidence_score=confidence_score,
                reason="conflicting_anchor_identifier",
            )

    if confidence_score >= auto_min:
        return DecisionResult("auto_link", version, confidence_score, "above_auto_threshold")
    elif confidence_score >= review_min:
        return DecisionResult("review_queue", version, confidence_score, "in_review_band")
    else:
        return DecisionResult("separate", version, confidence_score, "below_review_threshold")
