"""
UBID Platform — Review Service (Production)

Handles reviewer workflow with LLM-assisted summaries.
Captures reviewer decisions as training data for future threshold tuning.
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("ubid.review")


def build_review_context(
    record_a: dict,
    record_b: dict,
    evidence: dict,
    semantic_similarity: float,
) -> dict:
    """
    Build the complete context package for a reviewer.

    This is what the reviewer sees side-by-side in the UI.
    """
    return {
        "record_a": {
            "name": record_a.get("normalized_name"),
            "raw_name": record_a.get("raw_name"),
            "pan": record_a.get("pan"),
            "gstin": record_a.get("gstin"),
            "pincode": record_a.get("pincode"),
            "address": record_a.get("address_raw"),
            "source_system": record_a.get("source_system"),
        },
        "record_b": {
            "name": record_b.get("normalized_name"),
            "raw_name": record_b.get("raw_name"),
            "pan": record_b.get("pan"),
            "gstin": record_b.get("gstin"),
            "pincode": record_b.get("pincode"),
            "address": record_b.get("address_raw"),
            "source_system": record_b.get("source_system"),
        },
        "similarity_scores": {
            "semantic_embedding": round(semantic_similarity, 4),
            "token_overlap": evidence.get("token_overlap", 0),
            "fuzzy_name": evidence.get("fuzzy_name_similarity", 0),
            "address_overlap": evidence.get("address_overlap", 0),
        },
        "identifier_matches": {
            "pan_match": evidence.get("pan_match", False),
            "gstin_match": evidence.get("gstin_match", False),
            "pincode_match": evidence.get("pincode_match", False),
        },
        "matched_tokens": evidence.get("matched_tokens", []),
        "model_used": evidence.get("model_used", "nomic-embed-text"),
        "generated_at": datetime.utcnow().isoformat(),
    }


def build_training_record(
    evidence: dict,
    reviewer_decision: str,
    reviewer_id: str,
    pair_id: str,
) -> dict:
    """
    Build a training data record from a reviewer decision.

    This data is stored for future:
      - Threshold calibration
      - Analytics
      - Confidence tuning

    We do NOT train custom models yet — only collect the data.
    """
    return {
        "pair_id": pair_id,
        "semantic_similarity": evidence.get("semantic_similarity", 0),
        "token_overlap": evidence.get("token_overlap", 0),
        "fuzzy_name_similarity": evidence.get("fuzzy_name_similarity", 0),
        "address_overlap": evidence.get("address_overlap", 0),
        "pan_match": evidence.get("pan_match", False),
        "gstin_match": evidence.get("gstin_match", False),
        "pincode_match": evidence.get("pincode_match", False),
        "reviewer_decision": reviewer_decision,
        "reviewer_id": reviewer_id,
        "label": 1 if reviewer_decision == "confirm_match" else 0,
        "collected_at": datetime.utcnow().isoformat(),
    }
