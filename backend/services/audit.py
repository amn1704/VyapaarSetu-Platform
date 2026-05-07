"""UBID Platform — Audit Service (Module 13)"""

from datetime import datetime
from typing import Any, Optional


def make_audit_entry(
    action: str,
    entity_type: str,
    entity_id: str,
    actor: str = "system",
    before: Optional[Any] = None,
    after: Optional[Any] = None,
    extra_data: Optional[dict] = None,
) -> dict:
    """Build an audit log dict ready for DB insertion."""
    return {
        "action":       action,
        "entity_type":  entity_type,
        "entity_id":    str(entity_id),
        "actor":        actor,
        "before_state": before,
        "after_state":  after,
        "extra_data":   extra_data or {},
        "created_at":   datetime.utcnow(),
    }


# Convenience helpers
def audit_decision(pair_id: str, decision_type: str, score: float, actor: str = "system") -> dict:
    return make_audit_entry(
        action="decision_made", entity_type="candidate_pair",
        entity_id=pair_id, actor=actor,
        after={"decision_type": decision_type, "confidence_score": score},
    )


def audit_ubid_created(ubid_code: str) -> dict:
    return make_audit_entry(
        action="ubid_created", entity_type="ubid",
        entity_id=ubid_code, actor="system",
        after={"ubid_code": ubid_code},
    )


def audit_review_decision(queue_item_id: str, decision: str, reviewer_id: str) -> dict:
    return make_audit_entry(
        action="review_decision", entity_type="review_queue",
        entity_id=queue_item_id, actor=reviewer_id,
        after={"decision": decision},
    )


def audit_threshold_change(old: dict, new: dict, actor: str) -> dict:
    return make_audit_entry(
        action="threshold_config_changed", entity_type="threshold_config",
        entity_id=new.get("version", "unknown"),
        actor=actor, before=old, after=new,
    )


def audit_weight_deployed(version: str, actor: str) -> dict:
    return make_audit_entry(
        action="ml_weights_deployed", entity_type="ml_model_weights",
        entity_id=version, actor=actor,
    )
