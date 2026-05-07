"""
UBID Platform — AI Entity Matching Engine (Production)

Embeddings are the primary identity signal. Deterministic identifiers,
RapidFuzz, phonetics, address, and pincode are secondary validation and
explainability signals.

Replaces the old blocking → rapidfuzz scoring → weighted-decision pipeline.

Architecture:
  1. New record arrives → generate embedding
  2. pgvector cosine similarity search against all existing records
  3. Compute explainability evidence (token overlap, identifier match, etc.)
  4. Route: auto_match (≥0.92) | review_queue (0.75–0.91) | new_ubid (<0.75)
"""

# NOTE: The production API now uses services.scoring + services.decision for
# final business-match decisions. Helpers in this module are retained for
# candidate evidence and backward compatibility only.
import logging
import uuid
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field, asdict

import numpy as np

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

logger = logging.getLogger("ubid.matching")


# ── Thresholds ───────────────────────────────────────────────────────────────

AUTO_MATCH_THRESHOLD = 0.92
REVIEW_QUEUE_THRESHOLD = 0.75


# ── Result Types ─────────────────────────────────────────────────────────────

@dataclass
class MatchCandidate:
    """A potential match found via vector search."""
    record_id: str
    ubid_id: Optional[str]
    ubid_code: Optional[str]
    normalized_name: Optional[str]
    semantic_similarity: float
    evidence: dict
    decision: str  # auto_match | review_queue | new_ubid


@dataclass
class MatchResult:
    """Complete result of the matching pipeline for a new record."""
    new_record_id: str
    candidates: list[MatchCandidate]
    best_match: Optional[MatchCandidate]
    decision: str  # auto_match | review_queue | new_ubid
    model_used: str
    timestamp: str


# ── Explainability Evidence Builder ──────────────────────────────────────────

def _compute_token_overlap(name_a: Optional[str], name_b: Optional[str]) -> tuple[float, list[str]]:
    """Compute Jaccard token overlap and list of matched tokens."""
    if not name_a or not name_b:
        return 0.0, []
    tokens_a = set(name_a.lower().split())
    tokens_b = set(name_b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0, []
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0, sorted(intersection)


def _compute_fuzzy_similarity(name_a: Optional[str], name_b: Optional[str]) -> float:
    """Lightweight rapidfuzz fallback for explainability only."""
    if not name_a or not name_b:
        return 0.0
    if HAS_RAPIDFUZZ:
        return max(
            fuzz.ratio(name_a, name_b) / 100.0,
            fuzz.token_sort_ratio(name_a, name_b) / 100.0,
        )
    # Simple fallback
    tokens_a = set(name_a.split())
    tokens_b = set(name_b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    return 2 * len(tokens_a & tokens_b) / (len(tokens_a) + len(tokens_b))


def _exact_match(a: Optional[str], b: Optional[str]) -> bool:
    """Case-insensitive exact match for identifiers."""
    if not a or not b:
        return False
    return a.strip().upper() == b.strip().upper()


def _address_token_overlap(addr_a: Optional[dict], addr_b: Optional[dict]) -> float:
    """Token overlap between address components."""
    if not addr_a or not addr_b:
        return 0.0

    def _tokens(d: dict) -> set:
        text = " ".join(filter(None, [
            d.get("locality", ""), d.get("street", ""), d.get("building", ""),
        ]))
        return set(text.lower().split()) if text else set()

    ta, tb = _tokens(addr_a), _tokens(addr_b)
    if not ta or not tb:
        return 0.0
    return 2 * len(ta & tb) / (len(ta) + len(tb))


def build_evidence(
    new_record: dict,
    candidate: dict,
    semantic_similarity: float,
) -> dict:
    """
    Build a complete, explainable evidence JSON for a match candidate.

    Even though embeddings are the PRIMARY engine, this provides
    human-readable justification for every decision.
    """
    name_a = new_record.get("normalized_name")
    name_b = candidate.get("normalized_name")

    token_overlap, matched_tokens = _compute_token_overlap(name_a, name_b)
    fuzzy_sim = _compute_fuzzy_similarity(name_a, name_b)
    pan_match = _exact_match(new_record.get("pan"), candidate.get("pan"))
    gstin_match = _exact_match(new_record.get("gstin"), candidate.get("gstin"))
    pincode_match = _exact_match(new_record.get("pincode"), candidate.get("pincode"))
    address_overlap = _address_token_overlap(
        new_record.get("parsed_address"), candidate.get("parsed_address")
    )

    # Conflicting identifiers = hard block
    pan_conflict = False
    gstin_conflict = False
    if new_record.get("pan") and candidate.get("pan"):
        pan_conflict = not pan_match
    if new_record.get("gstin") and candidate.get("gstin"):
        gstin_conflict = not gstin_match

    return {
        "semantic_similarity": round(semantic_similarity, 4),
        "pan_match": pan_match,
        "gstin_match": gstin_match,
        "pan_conflict": pan_conflict,
        "gstin_conflict": gstin_conflict,
        "pincode_match": pincode_match,
        "token_overlap": round(token_overlap, 4),
        "matched_tokens": matched_tokens,
        "fuzzy_name_similarity": round(fuzzy_sim, 4),
        "address_overlap": round(address_overlap, 4),
        "new_record_name": name_a,
        "candidate_name": name_b,
        "model_used": "nomic-embed-text",
        "engine": "pgvector_cosine_similarity",
    }


# ── Decision Logic ───────────────────────────────────────────────────────────

def make_match_decision(
    semantic_similarity: float,
    evidence: dict,
    auto_threshold: float = AUTO_MATCH_THRESHOLD,
    review_threshold: float = REVIEW_QUEUE_THRESHOLD,
) -> str:
    """
    Decide the routing for a match candidate.

    HARD RULES (override similarity score):
      - Conflicting PAN → always separate (even if embedding says match)
      - Conflicting GSTIN → always separate
      - Exact PAN match → boost to auto_match if similarity ≥ 0.75

    SOFT RULES (threshold-based):
      - ≥ 0.92 → auto_match
      - 0.75 – 0.91 → review_queue
      - < 0.75 → new_ubid
    """
    # Hard block: conflicting identifiers
    if evidence.get("pan_conflict") or evidence.get("gstin_conflict"):
        return "new_ubid"

    # Boost: exact PAN/GSTIN match + reasonable similarity → auto
    if (evidence.get("pan_match") or evidence.get("gstin_match")) and semantic_similarity >= review_threshold:
        return "auto_match"

    # Standard threshold routing
    if semantic_similarity >= auto_threshold:
        return "auto_match"
    elif semantic_similarity >= review_threshold:
        return "review_queue"
    else:
        return "new_ubid"


# ── Cosine Similarity (pure numpy, for non-pgvector comparisons) ─────────

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not vec_a or not vec_b:
        return 0.0
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
