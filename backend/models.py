"""
UBID Platform — SQLAlchemy ORM Models (all 13 modules)
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Boolean, Integer, Text, DateTime, Date,
    ForeignKey, CheckConstraint, UniqueConstraint, Index, Computed,
    JSON, UUID
)
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from .database import Base

def _uuid():
    return str(uuid.uuid4())


# ── MODULE 1: RAW INGESTION ──────────────────────────────────────────────────

class RawRecord(Base):
    __tablename__ = "raw_records"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_system    = Column(Text, nullable=False)
    source_record_id = Column(Text, nullable=False)
    raw_payload      = Column(JSON, nullable=False)
    extracted_at     = Column(DateTime(timezone=True), default=datetime.utcnow)
    checksum         = Column(Text, nullable=False)

    normalized       = relationship("NormalizedRecord", back_populates="raw_record", uselist=False)
    record_links     = relationship("RecordLink", back_populates="raw_record")
    __table_args__   = (
        UniqueConstraint("source_system", "source_record_id", "checksum"),
        Index("ix_raw_records_source_record", "source_system", "source_record_id"),
        Index("ix_raw_records_extracted_at", "extracted_at"),
    )


# ── MODULE 2: NORMALIZATION ──────────────────────────────────────────────────

class NormalizedRecord(Base):
    __tablename__ = "normalized_records"
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_record_id   = Column(UUID(as_uuid=True), ForeignKey("raw_records.id", ondelete="CASCADE"), nullable=False)
    normalized_name = Column(Text)
    phonetic_name   = Column(Text)
    parsed_address  = Column(JSON)
    pincode         = Column(Text)
    pan             = Column(Text)
    latitude        = Column(Float)
    longitude       = Column(Float)
    gstin           = Column(Text)
    proprietor_name = Column(Text)
    sector          = Column(Text)
    pan_valid       = Column(Boolean, default=False)
    gstin_valid     = Column(Boolean, default=False)
    name_embedding = Column(Vector(768))
    address_embedding = Column(Vector(768))
    business_embedding = Column(Vector(768))
    embedding_vector = Column(Vector(768))  # Backward-compatible alias for business_embedding.
    normalized_at   = Column(DateTime(timezone=True), default=datetime.utcnow)

    raw_record  = relationship("RawRecord", back_populates="normalized")
    pairs_as_a  = relationship("CandidatePair", foreign_keys="CandidatePair.record_a_id", back_populates="record_a")
    pairs_as_b  = relationship("CandidatePair", foreign_keys="CandidatePair.record_b_id", back_populates="record_b")
    __table_args__ = (
        Index("ix_normalized_records_pan", "pan"),
        Index("ix_normalized_records_gstin", "gstin"),
        Index("ix_normalized_records_pincode", "pincode"),
        Index("ix_normalized_records_name", "normalized_name"),
    )


# ── MODULE 3: BLOCKING ───────────────────────────────────────────────────────

class CandidatePair(Base):
    __tablename__ = "candidate_pairs"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_a_id      = Column(UUID(as_uuid=True), ForeignKey("normalized_records.id"), nullable=False)
    record_b_id      = Column(UUID(as_uuid=True), ForeignKey("normalized_records.id"), nullable=False)
    blocking_strategy = Column(Text, nullable=False)
    created_at       = Column(DateTime(timezone=True), default=datetime.utcnow)

    record_a  = relationship("NormalizedRecord", foreign_keys=[record_a_id], back_populates="pairs_as_a")
    record_b  = relationship("NormalizedRecord", foreign_keys=[record_b_id], back_populates="pairs_as_b")
    scored    = relationship("ScoredPair", back_populates="pair", uselist=False)
    decision  = relationship("Decision", back_populates="pair", uselist=False)
    review_item = relationship("ReviewQueue", back_populates="pair", uselist=False)


# ── MODULE 4: SCORING ────────────────────────────────────────────────────────

class ScoredPair(Base):
    __tablename__ = "scored_pairs"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pair_id          = Column(UUID(as_uuid=True), ForeignKey("candidate_pairs.id", ondelete="CASCADE"), nullable=False)
    record_a_id      = Column(UUID(as_uuid=True), nullable=False)
    record_b_id      = Column(UUID(as_uuid=True), nullable=False)
    feature_vector   = Column(JSON, nullable=False)
    confidence_score = Column(Float, nullable=False)
    evidence_object  = Column(JSON, nullable=False)
    weight_version   = Column(Text, nullable=False, default="v1.0")
    scored_at        = Column(DateTime(timezone=True), default=datetime.utcnow)

    pair = relationship("CandidatePair", back_populates="scored")


# ── MODULE 5: DECISIONS ──────────────────────────────────────────────────────

class ThresholdConfig(Base):
    __tablename__ = "threshold_config"
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version         = Column(Text, nullable=False, unique=True)
    auto_link_min   = Column(Float, nullable=False, default=0.90)
    review_min      = Column(Float, nullable=False, default=0.60)
    deployed_at     = Column(DateTime(timezone=True), default=datetime.utcnow)
    deployed_by     = Column(Text, nullable=False, default="system")
    is_active       = Column(Boolean, nullable=False, default=True)


class Decision(Base):
    __tablename__ = "decisions"
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pair_id           = Column(UUID(as_uuid=True), ForeignKey("candidate_pairs.id"), nullable=False)
    scored_pair_id    = Column(UUID(as_uuid=True), ForeignKey("scored_pairs.id"), nullable=True)
    decision_type     = Column(Text, nullable=False)
    threshold_version = Column(Text, nullable=False)
    confidence_score  = Column(Float)
    created_at        = Column(DateTime(timezone=True), default=datetime.utcnow)
    reversed_at       = Column(DateTime(timezone=True))
    reversed_by       = Column(Text)

    pair = relationship("CandidatePair", back_populates="decision")
    __table_args__ = (
        CheckConstraint("decision_type IN ('auto_link','review_queue','separate')"),
    )


# ── MODULE 6: UBID REGISTRY ──────────────────────────────────────────────────

class UBID(Base):
    __tablename__ = "ubids"
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ubid_code    = Column(Text, nullable=False, unique=True)
    is_canonical = Column(Boolean, nullable=False, default=True)
    alias_of     = Column(UUID(as_uuid=True), ForeignKey("ubids.id"), nullable=True)
    pan          = Column(Text)
    gstin        = Column(Text)
    created_at   = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at   = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    record_links = relationship("RecordLink", back_populates="ubid")
    activity     = relationship("UBIDActivity", back_populates="ubid", uselist=False)


class RecordLink(Base):
    __tablename__ = "record_links"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ubid_id          = Column(UUID(as_uuid=True), ForeignKey("ubids.id"), nullable=False)
    raw_record_id    = Column(UUID(as_uuid=True), ForeignKey("raw_records.id"), nullable=False)
    source_system    = Column(Text, nullable=False)
    source_record_id = Column(Text, nullable=False)
    confidence       = Column(Float, nullable=False)
    decision_type    = Column(Text, nullable=False)
    linked_at        = Column(DateTime(timezone=True), default=datetime.utcnow)
    unlinked_at      = Column(DateTime(timezone=True))

    ubid       = relationship("UBID", back_populates="record_links")
    raw_record = relationship("RawRecord", back_populates="record_links")
    __table_args__ = (
        UniqueConstraint("ubid_id", "raw_record_id"),
        Index("ix_record_links_current_raw", "raw_record_id", "unlinked_at"),
        Index("ix_record_links_current_ubid", "ubid_id", "unlinked_at"),
    )


# ── MODULE 7: REVIEW WORKFLOW ────────────────────────────────────────────────

class ReviewQueue(Base):
    __tablename__ = "review_queue"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pair_id          = Column(UUID(as_uuid=True), ForeignKey("candidate_pairs.id"), nullable=False)
    scored_pair_id   = Column(UUID(as_uuid=True), ForeignKey("scored_pairs.id"), nullable=True)
    confidence_score = Column(Float, nullable=False)
    priority         = Column(Integer, nullable=False, default=0)
    status           = Column(Text, nullable=False, default="pending")
    reviewer_notes   = Column(Text)
    locked_by        = Column(Text)
    locked_at        = Column(DateTime(timezone=True))
    lock_expires_at  = Column(DateTime(timezone=True))
    queued_at        = Column(DateTime(timezone=True), default=datetime.utcnow)
    resolved_at      = Column(DateTime(timezone=True))

    pair     = relationship("CandidatePair", back_populates="review_item")
    decision = relationship("ReviewDecision", back_populates="queue_item", uselist=False)
    __table_args__ = (
        CheckConstraint("status IN ('pending','locked','resolved','deferred','escalated')"),
        Index("ix_review_queue_status_priority", "status", "priority", "queued_at"),
    )


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    queue_item_id = Column(UUID(as_uuid=True), ForeignKey("review_queue.id"), nullable=False)
    pair_id       = Column(UUID(as_uuid=True), ForeignKey("candidate_pairs.id"), nullable=False)
    decision      = Column(Text, nullable=False)
    justification = Column(Text)
    reviewer_id   = Column(Text, nullable=False)
    created_at    = Column(DateTime(timezone=True), default=datetime.utcnow)

    queue_item = relationship("ReviewQueue", back_populates="decision")


class LabeledPair(Base):
    __tablename__ = "labeled_pairs"
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pair_id        = Column(UUID(as_uuid=True), ForeignKey("candidate_pairs.id"), nullable=False)
    feature_vector = Column(JSON, nullable=False)
    label          = Column(Integer, nullable=False)  # 0 or 1
    metadata_json  = Column(JSON)
    source         = Column(Text, nullable=False, default="reviewer")
    created_at     = Column(DateTime(timezone=True), default=datetime.utcnow)


# ── MODULE 8: ML MODEL WEIGHTS ───────────────────────────────────────────────

class MLModelWeights(Base):
    __tablename__ = "ml_model_weights"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version       = Column(Text, nullable=False, unique=True)
    weights       = Column(JSON, nullable=False)
    intercept     = Column(Float, nullable=False, default=0.0)
    trained_on    = Column(Integer, nullable=False)
    precision_val = Column(Float)
    recall_val    = Column(Float)
    status        = Column(Text, nullable=False, default="pending_approval")
    created_at    = Column(DateTime(timezone=True), default=datetime.utcnow)
    approved_by   = Column(Text)
    approved_at   = Column(DateTime(timezone=True))
    deployed_at   = Column(DateTime(timezone=True))


# ── MODULE 9: EVENTS ─────────────────────────────────────────────────────────

class Event(Base):
    __tablename__ = "events"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_system    = Column(Text, nullable=False)
    source_record_id = Column(Text, nullable=False)
    event_type       = Column(Text, nullable=False)
    event_date       = Column(Date, nullable=False)
    payload          = Column(JSON)
    ingested_at      = Column(DateTime(timezone=True), default=datetime.utcnow)
    ubid_id          = Column(UUID(as_uuid=True), ForeignKey("ubids.id"), nullable=True)
    joined_at        = Column(DateTime(timezone=True))
    dedup_key        = Column(Text, unique=True)
    __table_args__ = (
        Index("ix_events_ubid_date", "ubid_id", "event_date"),
        Index("ix_events_source_record", "source_system", "source_record_id"),
    )


class PendingEvent(Base):
    __tablename__ = "pending_events"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id    = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, unique=True)
    reason      = Column(Text, nullable=False)
    retry_count = Column(Integer, nullable=False, default=0)
    last_tried  = Column(DateTime(timezone=True))
    created_at  = Column(DateTime(timezone=True), default=datetime.utcnow)


# ── MODULE 11: ACTIVITY CLASSIFIER ──────────────────────────────────────────

class SignalTaxonomy(Base):
    __tablename__ = "signal_taxonomy"
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type      = Column(Text, nullable=False, unique=True)
    signal_strength = Column(Text, nullable=False)
    decay_days      = Column(Integer, nullable=False, default=365)
    weight          = Column(Float, nullable=False, default=1.0)
    is_active       = Column(Boolean, nullable=False, default=True)


class UBIDActivity(Base):
    __tablename__ = "ubid_activity"
    ubid_id                = Column(UUID(as_uuid=True), ForeignKey("ubids.id"), primary_key=True)
    status                 = Column(Text, nullable=False)
    score                  = Column(Float, nullable=False)
    evidence_timeline      = Column(JSON, nullable=False)
    computed_at            = Column(DateTime(timezone=True), default=datetime.utcnow)
    reviewer_override      = Column(Text)
    override_by            = Column(Text)
    override_at            = Column(DateTime(timezone=True))
    override_justification = Column(Text)

    ubid = relationship("UBID", back_populates="activity")


# ── MODULE 13: AUDIT LOG ─────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action       = Column(Text, nullable=False)
    entity_type  = Column(Text, nullable=False)
    entity_id    = Column(Text, nullable=False)
    actor        = Column(Text, nullable=False, default="system")
    before_state = Column(JSON)
    after_state  = Column(JSON)
    extra_data   = Column(JSON)
    created_at   = Column(DateTime(timezone=True), default=datetime.utcnow)
