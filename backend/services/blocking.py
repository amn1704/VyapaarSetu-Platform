"""
UBID Platform — Optimized Blocking Engine (Module 3)

Performance improvements:
- O(N) index build instead of O(N²) naive comparison
- Inverted index (hash map) based blocking: only pairs sharing a key are compared
- Sorted Neighborhood Window for fuzzy name blocking
- Early-exit deduplication via set-based seen pairs
- Result: reduces candidate pairs from O(N²) to O(N + K) where K << N²
"""

from typing import Optional
import unicodedata
import re


# ── Utility Functions ─────────────────────────────────────────────────────────

def _normalize_key(s: str) -> str:
    """Lowercase, strip accents/special chars, collapse whitespace."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9\s]", "", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def _name_prefix_key(name: str, prefix_len: int = 8) -> str:
    """Extract first N chars of normalized name for prefix blocking."""
    normalized = _normalize_key(name)
    tokens = normalized.split()
    return "".join(tokens)[:prefix_len] if tokens else ""


# ── Core Blocking Engine ───────────────────────────────────────────────────────

def generate_candidate_pairs(normalized_records: list[dict]) -> list[dict]:
    """
    Generate candidate pairs using 4 inverted-index blocking strategies (UNION).

    Complexity:
      - Building indexes:  O(N) per strategy
      - Pair generation:   O(N + K) where K = average bucket size (small)
      - Total:             O(N) amortized vs O(N²) naive

    Args:
        normalized_records: list of dicts with keys matching NormalizedRecord fields

    Returns:
        Deduplicated list of candidate pairs with their blocking strategy label.
    """
    seen: set[tuple] = set()
    pairs: list[dict] = []

    def add_pair(a_id: str, b_id: str, strategy: str):
        # Canonical ordering ensures (A,B) == (B,A)
        key = (min(a_id, b_id), max(a_id, b_id))
        if key not in seen:
            seen.add(key)
            pairs.append({
                "record_a_id": key[0],
                "record_b_id": key[1],
                "blocking_strategy": strategy,
            })

    def index_and_pair(get_key, strategy: str, min_bucket_size: int = 2, max_bucket_size: int = 50):
        """
        Build an inverted index from records, then emit pairs within each bucket.
        max_bucket_size cap prevents O(K²) explosion in pathological buckets
        (e.g. 1000 records all named "SHOP" would create 500K pairs).
        """
        index: dict[str, list[str]] = {}
        for rec in normalized_records:
            k = get_key(rec)
            if k:
                index.setdefault(k, []).append(str(rec["id"]))

        for key_val, ids in index.items():
            if len(ids) < min_bucket_size:
                continue
            # Cap very large buckets: take only the first max_bucket_size records
            capped = ids[:max_bucket_size]
            for i in range(len(capped)):
                for j in range(i + 1, len(capped)):
                    add_pair(capped[i], capped[j], strategy)

    # ── Strategy 1: PAN exact match (highest precision) ──────────────────────
    index_and_pair(
        lambda r: r.get("pan") if r.get("pan_valid") else None,
        "pan_exact",
        max_bucket_size=100,  # PAN should be unique, small buckets OK
    )

    # ── Strategy 2: GSTIN exact match ─────────────────────────────────────────
    index_and_pair(
        lambda r: r.get("gstin") if r.get("gstin_valid") else None,
        "gstin_exact",
        max_bucket_size=100,
    )

    # ── Strategy 3: Pincode + Name-Prefix (locality blocking) ─────────────────
    def pincode_name_key(rec: dict) -> Optional[str]:
        pin = rec.get("pincode")
        name = rec.get("normalized_name", "")
        prefix = _name_prefix_key(name, prefix_len=6)
        return f"{pin}::{prefix}" if pin and prefix else None

    index_and_pair(
        pincode_name_key,
        "pincode_name",
        max_bucket_size=30,  # Tight locality keeps pairs manageable
    )

    # ── Strategy 4: Phonetic name match ───────────────────────────────────────
    index_and_pair(
        lambda r: r.get("phonetic_name"),
        "phonetic",
        max_bucket_size=25,
    )

    # ── Strategy 5: Sorted Neighborhood on normalized name (fuzzy prefix) ─────
    # Sort all records by normalized name, slide a window of size W.
    # This catches near-duplicates that differ only in 1–2 characters.
    WINDOW = 5
    sorted_recs = sorted(
        [(r.get("normalized_name") or "", str(r["id"])) for r in normalized_records],
        key=lambda x: _normalize_key(x[0])
    )
    for i, (name_i, id_i) in enumerate(sorted_recs):
        for j in range(i + 1, min(i + WINDOW + 1, len(sorted_recs))):
            name_j, id_j = sorted_recs[j]
            # Only pair if first tokens share the same 4-char prefix (efficiency gate)
            pi = _name_prefix_key(name_i, 4)
            pj = _name_prefix_key(name_j, 4)
            if pi and pj and pi == pj:
                add_pair(id_i, id_j, "sorted_neighborhood")

    return pairs
