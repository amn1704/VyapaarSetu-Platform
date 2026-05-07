"""
UBID Platform — Similarity Scoring Engine (Module 4)

Computes a weighted confidence score for each candidate pair.
Evidence object is fully explainable and stored with every decision.
"""

from typing import Optional
from dataclasses import dataclass

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

import numpy as np

# ── Default feature weights (overridden by ML feedback loop) ─────────────────

DEFAULT_WEIGHTS = {
    "pan_gstin_match":       0.50,
    "embedding_similarity":  0.20,
    "name_similarity":       0.10,
    "address_overlap":       0.10,
    "phonetic_match":        0.05,
    "pincode_match":         0.05,
}

# Normalisation: when both PAN and GSTIN are absent, redistribute their weight
_ANCHOR_FEATURES = {"pan_gstin_match"}


@dataclass
class ScoringResult:
    feature_vector:  dict
    confidence_score: float
    evidence_object:  dict


# ── Individual feature functions ──────────────────────────────────────────────

def _name_similarity(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0
    if HAS_RAPIDFUZZ:
        jaro   = fuzz.ratio(a, b) / 100.0
        token  = fuzz.token_sort_ratio(a, b) / 100.0
        return max(jaro, token)
    # Fallback: simple character overlap ratio
    set_a, set_b = set(a.split()), set(b.split())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    return 2 * len(intersection) / (len(set_a) + len(set_b))


def _exact_match(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0
    return 1.0 if a.strip().upper() == b.strip().upper() else 0.0


def _phonetic_match(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0
    codes_a = {part for chunk in a.split("|") for part in chunk.replace("DM:", "").replace("SX:", "").split()}
    codes_b = {part for chunk in b.split("|") for part in chunk.replace("DM:", "").replace("SX:", "").split()}
    if not codes_a or not codes_b:
        return 0.0
    return len(codes_a & codes_b) / len(codes_a | codes_b)


def _address_overlap(addr_a: Optional[dict], addr_b: Optional[dict]) -> float:
    """Token overlap between locality and street fields."""
    if not addr_a or not addr_b:
        return 0.0

    def tokens(d: dict) -> set:
        text = " ".join(filter(None, [
            d.get("locality"), d.get("street"), d.get("building")
        ]))
        return set(text.lower().split()) if text else set()

    ta, tb = tokens(addr_a), tokens(addr_b)
    if not ta or not tb:
        return 0.0
    return 2 * len(ta & tb) / (len(ta) + len(tb))

def _cosine_similarity(vec_a: Optional[list[float]], vec_b: Optional[list[float]]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    a, b = np.array(vec_a), np.array(vec_b)
    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# ── Main scoring function ─────────────────────────────────────────────────────

def score_pair(
    rec_a: dict,
    rec_b: dict,
    weights: Optional[dict] = None,
    weight_version: str = "v1.0",
) -> ScoringResult:
    """
    Compute confidence score for a pair of normalized records.

    Args:
        rec_a / rec_b: dicts with keys matching NormalizedRecord fields
        weights: optional overriding weight dict (from ML feedback)
        weight_version: label for audit trail

    Returns:
        ScoringResult with feature_vector, confidence_score, and evidence_object
    """
    w = weights or DEFAULT_WEIGHTS.copy()

    # ── Compute individual features ──
    pan_match        = _exact_match(rec_a.get("pan"), rec_b.get("pan"))
    gstin_match      = _exact_match(rec_a.get("gstin"), rec_b.get("gstin"))
    pan_gstin_match  = max(pan_match, gstin_match)
    
    embed_sim        = _cosine_similarity(rec_a.get("embedding_vector"), rec_b.get("embedding_vector"))
    name_sim         = _name_similarity(rec_a.get("normalized_name"), rec_b.get("normalized_name"))
    phonetic         = _phonetic_match(rec_a.get("phonetic_name"), rec_b.get("phonetic_name"))
    pincode_match    = _exact_match(rec_a.get("pincode"), rec_b.get("pincode"))
    address_overlap  = _address_overlap(rec_a.get("parsed_address"), rec_b.get("parsed_address"))

    feature_vector = {
        "pan_gstin_match":      pan_gstin_match,
        "embedding_similarity": round(embed_sim, 4),
        "name_similarity":      round(name_sim, 4),
        "phonetic_match":       phonetic,
        "pincode_match":        pincode_match,
        "address_overlap":      round(address_overlap, 4),
    }

    # ── Reweight if anchor identifiers absent ────────────────────────────────
    # If both PAN and GSTIN are missing for both records, redistribute the
    # anchor weight proportionally to non-anchor features to avoid always
    # scoring low simply due to missing data.
    effective_weights = w.copy()
    pan_absent  = not rec_a.get("pan")  and not rec_b.get("pan")
    gstin_absent = not rec_a.get("gstin") and not rec_b.get("gstin")

    redistributed = 0.0
    if pan_absent and gstin_absent:
        redistributed += effective_weights.pop("pan_gstin_match", 0)

    if redistributed > 0:
        non_anchor = {k: v for k, v in effective_weights.items()}
        total_non_anchor = sum(non_anchor.values()) or 1.0
        for k in non_anchor:
            effective_weights[k] += redistributed * (effective_weights[k] / total_non_anchor)

    # ── Compute weighted score ────────────────────────────────────────────────
    contributions = {}
    score = 0.0
    for feature, value in feature_vector.items():
        fw = effective_weights.get(feature, 0.0)
        contribution = value * fw
        contributions[feature] = round(contribution, 4)
        score += contribution

    # Hard rule: conflicting anchors → cap score at review threshold
    # (one PAN present but different from other)
    pan_a, pan_b = rec_a.get("pan"), rec_b.get("pan")
    if pan_a and pan_b and pan_a.upper() != pan_b.upper():
        score = min(score, 0.40)  # force to 'separate' range

    gstin_a, gstin_b = rec_a.get("gstin"), rec_b.get("gstin")
    if gstin_a and gstin_b and gstin_a.upper() != gstin_b.upper():
        score = min(score, 0.40)

    confidence_score = round(min(max(score, 0.0), 1.0), 4)

    evidence_object = {
        "features":      feature_vector,
        "weights":       effective_weights,
        "contributions": contributions,
        "weight_version": weight_version,
        "anchor_redistributed": pan_absent and gstin_absent,
        "conflicting_pan":   bool(pan_a and pan_b and pan_a.upper() != pan_b.upper()),
        "conflicting_gstin": bool(gstin_a and gstin_b and gstin_a.upper() != gstin_b.upper()),
    }

    return ScoringResult(
        feature_vector   = feature_vector,
        confidence_score = confidence_score,
        evidence_object  = evidence_object,
    )
