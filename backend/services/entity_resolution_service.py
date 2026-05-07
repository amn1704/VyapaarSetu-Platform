"""
Embedding-first UBID entity resolution.

This is the production identity engine for the UBID platform. It uses
nomic-embed-text vectors and pgvector cosine search as the primary matching
mechanism. RapidFuzz, phonetic encodings, identifiers, and address overlap are
secondary evidence signals for explainability and safety guardrails.

The LLM is never used here.
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import settings
from ..models import (
    AuditLog,
    CandidatePair,
    Decision,
    LabeledPair,
    NormalizedRecord,
    RawRecord,
    RecordLink,
    ReviewQueue,
    ScoredPair,
    UBID,
    UBIDActivity,
)
from .audit import audit_ubid_created, make_audit_entry
from .embedding_service import build_identity_text, generate_embedding
from .event_bus import publish_event
from .ubid_service import generate_ubid_code

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

logger = logging.getLogger("ubid.entity_resolution")


@dataclass(frozen=True)
class CandidateHit:
    record: NormalizedRecord
    semantic_similarity: float


@dataclass(frozen=True)
class ResolutionResult:
    record_id: str
    decision: str
    confidence: float
    ubid: Optional[str]
    evidence: dict


def normalized_record_to_texts(norm: NormalizedRecord, raw_payload: Optional[dict] = None) -> dict[str, str]:
    """Build the embedding inputs used by the AI-first resolver."""
    raw_payload = raw_payload or {}
    normalized_address = norm.parsed_address.get("raw") if norm.parsed_address else ""
    sector = norm.sector or raw_payload.get("sector") or raw_payload.get("business_activity") or ""
    proprietor = norm.proprietor_name or ""

    name_text = norm.normalized_name or ""
    address_text = normalized_address or ""
    business_text = build_identity_text(
        normalized_name=norm.normalized_name,
        address_raw=normalized_address,
        sector=sector,
    )
    if proprietor:
        business_text = f"{business_text} proprietor {proprietor}".strip()

    return {
        "name": name_text,
        "address": address_text,
        "business": business_text or name_text or address_text,
    }


async def ensure_embeddings(norm: NormalizedRecord, raw_payload: Optional[dict] = None) -> None:
    """Generate missing name/address/business embeddings through local Ollama."""
    texts = normalized_record_to_texts(norm, raw_payload)

    if not _as_vector(norm.name_embedding) and texts["name"]:
        norm.name_embedding = await generate_embedding(texts["name"])
    if not _as_vector(norm.address_embedding) and texts["address"]:
        norm.address_embedding = await generate_embedding(texts["address"])
    if not _as_vector(norm.business_embedding) and texts["business"]:
        norm.business_embedding = await generate_embedding(texts["business"])

    # Backward compatibility for older code/views.
    if not _as_vector(norm.embedding_vector) and _as_vector(norm.business_embedding):
        norm.embedding_vector = norm.business_embedding


def _as_vector(value) -> list[float]:
    if value is None:
        return []
    try:
        return list(value)
    except TypeError:
        return value


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(x):.8f}" for x in vector) + "]"


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(float(a) * float(a) for a in vec_a))
    norm_b = math.sqrt(sum(float(b) * float(b) for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def _exact_match(a: Optional[str], b: Optional[str]) -> bool:
    return bool(a and b and a.strip().upper() == b.strip().upper())


def _identifier_conflict(a: Optional[str], b: Optional[str]) -> bool:
    return bool(a and b and a.strip().upper() != b.strip().upper())


def _token_overlap(a: Optional[str], b: Optional[str]) -> tuple[float, list[str]]:
    if not a or not b:
        return 0.0, []
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0, []
    matched = sorted(tokens_a & tokens_b)
    return len(matched) / len(tokens_a | tokens_b), matched


def _fuzzy_name_similarity(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0
    if HAS_RAPIDFUZZ:
        return max(fuzz.ratio(a, b), fuzz.token_sort_ratio(a, b)) / 100.0
    overlap, _ = _token_overlap(a, b)
    return overlap


def _phonetic_similarity(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0
    codes_a = set(a.replace("DM:", "").replace("SX:", "").replace("|", " ").split())
    codes_b = set(b.replace("DM:", "").replace("SX:", "").replace("|", " ").split())
    if not codes_a or not codes_b:
        return 0.0
    return len(codes_a & codes_b) / len(codes_a | codes_b)


def _address_overlap(a: Optional[dict], b: Optional[dict]) -> float:
    if not a or not b:
        return 0.0

    def tokens(value: dict) -> set[str]:
        text_value = " ".join(
            str(value.get(k) or "") for k in ("raw", "building", "street", "locality", "city")
        )
        return set(text_value.lower().split())

    tokens_a = tokens(a)
    tokens_b = tokens(b)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def build_embedding_evidence(new_record: NormalizedRecord, candidate: NormalizedRecord, semantic_similarity: float) -> dict:
    """Build government-grade explainability JSON for an embedding match."""
    token_overlap, matched_tokens = _token_overlap(new_record.normalized_name, candidate.normalized_name)
    pan_match = _exact_match(new_record.pan, candidate.pan)
    gstin_match = _exact_match(new_record.gstin, candidate.gstin)
    pan_conflict = _identifier_conflict(new_record.pan, candidate.pan)
    gstin_conflict = _identifier_conflict(new_record.gstin, candidate.gstin)

    evidence = {
        "semantic_similarity": round(semantic_similarity, 4),
        "pan_match": pan_match,
        "gstin_match": gstin_match,
        "pan_conflict": pan_conflict,
        "gstin_conflict": gstin_conflict,
        "address_overlap": round(_address_overlap(new_record.parsed_address, candidate.parsed_address), 4),
        "token_overlap": round(token_overlap, 4),
        "phonetic_similarity": round(_phonetic_similarity(new_record.phonetic_name, candidate.phonetic_name), 4),
        "fuzzy_name_similarity": round(_fuzzy_name_similarity(new_record.normalized_name, candidate.normalized_name), 4),
        "pincode_match": _exact_match(new_record.pincode, candidate.pincode),
        "matched_tokens": matched_tokens,
        "new_record": {
            "id": str(new_record.id),
            "normalized_name": new_record.normalized_name,
            "pincode": new_record.pincode,
            "pan": new_record.pan,
            "gstin": new_record.gstin,
        },
        "candidate_record": {
            "id": str(candidate.id),
            "normalized_name": candidate.normalized_name,
            "pincode": candidate.pincode,
            "pan": candidate.pan,
            "gstin": candidate.gstin,
        },
        "primary_engine": "pgvector_cosine_similarity",
        "embedding_model": settings.EMBEDDING_MODEL,
        "llm_used_for_matching": False,
        "computed_at": datetime.utcnow().isoformat(),
    }

    if pan_conflict or gstin_conflict:
        evidence["guardrail"] = "identifier_conflict_blocks_auto_match"
    return evidence


def route_embedding_match(semantic_similarity: float, evidence: dict) -> str:
    """Route by embedding similarity, with identifier conflicts forcing review."""
    if evidence.get("pan_conflict") or evidence.get("gstin_conflict"):
        return "review_queue" if semantic_similarity >= settings.REVIEW_QUEUE_THRESHOLD else "new_ubid"
    if semantic_similarity >= settings.AUTO_MATCH_THRESHOLD:
        return "auto_match"
    if semantic_similarity >= settings.REVIEW_QUEUE_THRESHOLD:
        return "review_queue"
    return "new_ubid"


async def vector_search_candidates(norm: NormalizedRecord, db: AsyncSession) -> list[CandidateHit]:
    """Search pgvector for nearest business embeddings; fall back to bounded in-memory cosine for dev SQLite."""
    vector = _as_vector(norm.business_embedding) or _as_vector(norm.embedding_vector)
    if not vector:
        return []

    bind = db.get_bind()
    backend = bind.url.get_backend_name() if bind is not None else ""
    if backend.startswith("postgresql"):
        result = await db.execute(
            text("""
                SELECT id, 1 - (business_embedding <=> :vec::vector) AS similarity
                FROM normalized_records
                WHERE id != :record_id
                  AND business_embedding IS NOT NULL
                ORDER BY business_embedding <=> :vec::vector
                LIMIT :limit
            """),
            {
                "vec": _vector_literal(vector),
                "record_id": str(norm.id),
                "limit": settings.VECTOR_SEARCH_LIMIT,
            },
        )
        rows = result.fetchall()
        ids = [row.id for row in rows]
        similarity_by_id = {str(row.id): float(row.similarity or 0.0) for row in rows}
        if not ids:
            return []
        records = await db.execute(
            select(NormalizedRecord)
            .options(selectinload(NormalizedRecord.raw_record))
            .where(NormalizedRecord.id.in_(ids))
        )
        by_id = {str(record.id): record for record in records.scalars().all()}
        return [
            CandidateHit(record=by_id[str(record_id)], semantic_similarity=similarity_by_id[str(record_id)])
            for record_id in ids
            if str(record_id) in by_id
        ]

    # Development fallback: bounded scan. Production PostgreSQL uses pgvector above.
    result = await db.execute(
        select(NormalizedRecord)
        .options(selectinload(NormalizedRecord.raw_record))
        .where(NormalizedRecord.id != norm.id)
        .order_by(NormalizedRecord.normalized_at.desc())
        .limit(1000)
    )
    hits = []
    for candidate in result.scalars().all():
        candidate_vector = _as_vector(candidate.business_embedding) or _as_vector(candidate.embedding_vector)
        similarity = _cosine_similarity(vector, candidate_vector)
        hits.append(CandidateHit(record=candidate, semantic_similarity=similarity))
    hits.sort(key=lambda hit: hit.semantic_similarity, reverse=True)
    return hits[: settings.VECTOR_SEARCH_LIMIT]


async def _get_record_link(raw_record_id: uuid.UUID, db: AsyncSession) -> Optional[RecordLink]:
    result = await db.execute(
        select(RecordLink).where(
            and_(RecordLink.raw_record_id == raw_record_id, RecordLink.unlinked_at.is_(None))
        )
    )
    return result.scalar_one_or_none()


async def _get_next_sequence(db: AsyncSession) -> int:
    year = datetime.utcnow().year
    prefix = f"UBID-KA-29-{year}"
    result = await db.execute(select(func.count(UBID.id)).where(UBID.ubid_code.like(f"{prefix}%")))
    return (result.scalar() or 0) + 1


async def _create_ubid_for_records(records: list[NormalizedRecord], db: AsyncSession, confidence: float, decision_type: str) -> UBID:
    sequence = await _get_next_sequence(db)
    code = generate_ubid_code(sequence)
    ubid = UBID(ubid_code=code)
    for record in records:
        if record.pan_valid and record.pan and not ubid.pan:
            ubid.pan = record.pan.upper()
        if record.gstin_valid and record.gstin and not ubid.gstin:
            ubid.gstin = record.gstin.upper()
    db.add(ubid)
    await db.flush()

    for record in records:
        existing = await _get_record_link(record.raw_record_id, db)
        if existing:
            continue
        db.add(RecordLink(
            ubid_id=ubid.id,
            raw_record_id=record.raw_record_id,
            source_system=record.raw_record.source_system,
            source_record_id=record.raw_record.source_record_id,
            confidence=confidence,
            decision_type=decision_type,
        ))

    db.add(UBIDActivity(
        ubid_id=ubid.id,
        status="Dormant",
        score=0.0,
        evidence_timeline=[{
            "event_id": "system",
            "event_type": "ubid_created",
            "event_date": datetime.utcnow().date().isoformat(),
            "source_system": "system",
            "signal_strength": "Info",
            "raw_weight": 0.0,
            "days_old": 0,
            "decay_weight": 0.0,
        }],
    ))
    db.add(AuditLog(**audit_ubid_created(code)))
    return ubid


async def _link_to_existing_ubid(new_record: NormalizedRecord, candidate: NormalizedRecord, confidence: float, db: AsyncSession) -> UBID:
    candidate_link = await _get_record_link(candidate.raw_record_id, db)
    if not candidate_link:
        return await _create_ubid_for_records([candidate, new_record], db, confidence, "embedding_auto_match")

    ubid = (await db.execute(select(UBID).where(UBID.id == candidate_link.ubid_id))).scalar_one()
    existing = await _get_record_link(new_record.raw_record_id, db)
    if not existing:
        db.add(RecordLink(
            ubid_id=ubid.id,
            raw_record_id=new_record.raw_record_id,
            source_system=new_record.raw_record.source_system,
            source_record_id=new_record.raw_record.source_record_id,
            confidence=confidence,
            decision_type="embedding_auto_match",
        ))
    return ubid


async def _upsert_pair_and_score(
    new_record: NormalizedRecord,
    candidate: NormalizedRecord,
    evidence: dict,
    decision_type: str,
    db: AsyncSession,
) -> tuple[CandidatePair, ScoredPair, Decision]:
    existing = await db.execute(
        select(CandidatePair).where(
            or_(
                and_(CandidatePair.record_a_id == new_record.id, CandidatePair.record_b_id == candidate.id),
                and_(CandidatePair.record_a_id == candidate.id, CandidatePair.record_b_id == new_record.id),
            )
        )
    )
    pair = existing.scalar_one_or_none()
    if not pair:
        pair = CandidatePair(
            record_a_id=new_record.id,
            record_b_id=candidate.id,
            blocking_strategy="pgvector_business_embedding",
        )
        db.add(pair)
        await db.flush()

    scored = ScoredPair(
        pair_id=pair.id,
        record_a_id=new_record.id,
        record_b_id=candidate.id,
        feature_vector={
            "semantic_similarity": evidence["semantic_similarity"],
            "pan_match": float(evidence["pan_match"]),
            "gstin_match": float(evidence["gstin_match"]),
            "address_overlap": evidence["address_overlap"],
            "token_overlap": evidence["token_overlap"],
            "phonetic_similarity": evidence["phonetic_similarity"],
            "fuzzy_name_similarity": evidence["fuzzy_name_similarity"],
            "pincode_match": float(evidence["pincode_match"]),
        },
        confidence_score=evidence["semantic_similarity"],
        evidence_object=evidence,
        weight_version="embedding-primary-v1",
    )
    db.add(scored)
    await db.flush()

    decision = Decision(
        pair_id=pair.id,
        scored_pair_id=scored.id,
        decision_type="auto_link" if decision_type == "auto_match" else decision_type,
        threshold_version="embedding-primary-v1",
        confidence_score=evidence["semantic_similarity"],
    )
    db.add(decision)
    return pair, scored, decision


async def _enqueue_review(pair: CandidatePair, scored: ScoredPair, evidence: dict, db: AsyncSession) -> ReviewQueue:
    existing = await db.execute(
        select(ReviewQueue).where(
            and_(ReviewQueue.pair_id == pair.id, ReviewQueue.status.in_(("pending", "locked", "deferred", "escalated")))
        )
    )
    item = existing.scalar_one_or_none()
    if item:
        item.confidence_score = evidence["semantic_similarity"]
        item.scored_pair_id = scored.id
        item.priority = max(item.priority or 0, int(evidence["semantic_similarity"] * 100))
        return item

    item = ReviewQueue(
        pair_id=pair.id,
        scored_pair_id=scored.id,
        confidence_score=evidence["semantic_similarity"],
        priority=int(evidence["semantic_similarity"] * 100),
        status="pending",
        reviewer_notes="Embedding-primary ambiguous match. Requires officer decision.",
    )
    db.add(item)
    return item


async def resolve_record(norm_id: uuid.UUID, db: AsyncSession) -> ResolutionResult:
    """Run embedding-first resolution for one normalized record."""
    result = await db.execute(
        select(NormalizedRecord)
        .options(selectinload(NormalizedRecord.raw_record))
        .where(NormalizedRecord.id == norm_id)
    )
    new_record = result.scalar_one_or_none()
    if not new_record:
        raise ValueError(f"normalized record not found: {norm_id}")

    if await _get_record_link(new_record.raw_record_id, db):
        return ResolutionResult(str(new_record.id), "already_linked", 1.0, None, {})

    await ensure_embeddings(new_record, new_record.raw_record.raw_payload if new_record.raw_record else {})
    hits = await vector_search_candidates(new_record, db)
    best = hits[0] if hits else None

    if not best or best.semantic_similarity < settings.REVIEW_QUEUE_THRESHOLD:
        if best:
            low_confidence_evidence = build_embedding_evidence(new_record, best.record, best.semantic_similarity)
            low_confidence_evidence["decision"] = "separate"
            low_confidence_evidence["reason"] = "best_embedding_candidate_below_review_threshold"
            await _upsert_pair_and_score(new_record, best.record, low_confidence_evidence, "separate", db)

        ubid = await _create_ubid_for_records([new_record], db, 1.0, "embedding_new_ubid")
        evidence = {
            "decision": "new_ubid",
            "reason": "no_embedding_candidate_above_review_threshold",
            "best_semantic_similarity": round(best.semantic_similarity, 4) if best else 0.0,
            "thresholds": {
                "auto_match": settings.AUTO_MATCH_THRESHOLD,
                "review_queue": settings.REVIEW_QUEUE_THRESHOLD,
            },
            "embedding_model": settings.EMBEDDING_MODEL,
            "computed_at": datetime.utcnow().isoformat(),
        }
        db.add(AuditLog(**make_audit_entry(
            action="embedding_new_ubid",
            entity_type="normalized_record",
            entity_id=str(new_record.id),
            actor="system",
            after={"ubid": ubid.ubid_code},
            extra_data=evidence,
        )))
        await publish_event("ubid.entity_resolution", evidence)
        await db.flush()
        return ResolutionResult(str(new_record.id), "new_ubid", 1.0, ubid.ubid_code, evidence)

    evidence = build_embedding_evidence(new_record, best.record, best.semantic_similarity)
    decision_type = route_embedding_match(best.semantic_similarity, evidence)
    evidence["decision"] = decision_type
    evidence["thresholds"] = {
        "auto_match": settings.AUTO_MATCH_THRESHOLD,
        "review_queue": settings.REVIEW_QUEUE_THRESHOLD,
    }

    pair, scored, _ = await _upsert_pair_and_score(new_record, best.record, evidence, decision_type, db)

    if decision_type == "auto_match":
        ubid = await _link_to_existing_ubid(new_record, best.record, best.semantic_similarity, db)
        db.add(AuditLog(**make_audit_entry(
            action="embedding_auto_match",
            entity_type="normalized_record",
            entity_id=str(new_record.id),
            actor="system",
            after={"ubid": ubid.ubid_code, "matched_record_id": str(best.record.id)},
            extra_data=evidence,
        )))
        await publish_event("ubid.entity_resolution", evidence)
        await db.flush()
        return ResolutionResult(str(new_record.id), "auto_match", best.semantic_similarity, ubid.ubid_code, evidence)

    if decision_type == "review_queue":
        item = await _enqueue_review(pair, scored, evidence, db)
        db.add(AuditLog(**make_audit_entry(
            action="embedding_review_queue",
            entity_type="review_queue",
            entity_id=str(item.id),
            actor="system",
            after={"queue_item_id": str(item.id), "matched_record_id": str(best.record.id)},
            extra_data=evidence,
        )))
        await publish_event("ubid.entity_resolution", evidence)
        await db.flush()
        return ResolutionResult(str(new_record.id), "review_queue", best.semantic_similarity, None, evidence)

    # This branch is rare because low similarity was handled above. Keep it for guardrails.
    ubid = await _create_ubid_for_records([new_record], db, 1.0, "embedding_new_ubid")
    evidence["decision"] = "new_ubid"
    db.add(AuditLog(**make_audit_entry(
        action="embedding_new_ubid",
        entity_type="normalized_record",
        entity_id=str(new_record.id),
        actor="system",
        after={"ubid": ubid.ubid_code},
        extra_data=evidence,
    )))
    await publish_event("ubid.entity_resolution", evidence)
    await db.flush()
    return ResolutionResult(str(new_record.id), "new_ubid", 1.0, ubid.ubid_code, evidence)


async def collect_review_training_example(
    pair_id: uuid.UUID,
    label: int,
    reviewer_id: str,
    db: AsyncSession,
) -> None:
    """Store reviewer feedback for future threshold calibration and analytics."""
    scored = (await db.execute(select(ScoredPair).where(ScoredPair.pair_id == pair_id))).scalar_one_or_none()
    if not scored:
        return
    db.add(LabeledPair(
        pair_id=pair_id,
        feature_vector=scored.feature_vector,
        label=label,
        source="reviewer",
        metadata_json={
            "reviewer_id": reviewer_id,
            "embedding_model": settings.EMBEDDING_MODEL,
            "threshold_version": "embedding-primary-v1",
            "collected_at": datetime.utcnow().isoformat(),
            "semantic_similarity": scored.evidence_object.get("semantic_similarity") if scored.evidence_object else None,
        },
    ))
