"""
Celery worker entrypoint for UBID background AI jobs.

The FastAPI app can use lightweight BackgroundTasks for local development, while
production deployments can enqueue these tasks through Redis-backed Celery.
"""

from __future__ import annotations

import asyncio
import uuid

from celery import Celery
from sqlalchemy import and_, select

from .config import settings
from .database import AsyncSessionLocal
from .models import NormalizedRecord, RawRecord, RecordLink
from .services.entity_resolution_service import ensure_embeddings, resolve_record
from .services.normalization import normalize_record

celery_app = Celery(
    "ubid_ai_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
)


async def _normalize_and_resolve(raw_record_id: str) -> dict:
    async with AsyncSessionLocal() as db:
        raw = (await db.execute(select(RawRecord).where(RawRecord.id == uuid.UUID(raw_record_id)))).scalar_one_or_none()
        if not raw:
            return {"status": "not_found", "raw_record_id": raw_record_id}

        existing = (await db.execute(
            select(NormalizedRecord).where(NormalizedRecord.raw_record_id == raw.id)
        )).scalar_one_or_none()
        if existing:
            result = await resolve_record(existing.id, db)
            await db.commit()
            return {"status": "resolved", "record_id": result.record_id, "decision": result.decision}

        norm_result = normalize_record(raw.raw_payload)
        norm = NormalizedRecord(
            raw_record_id=raw.id,
            sector=raw.raw_payload.get("sector") or raw.raw_payload.get("business_activity"),
            **norm_result.__dict__,
        )
        await ensure_embeddings(norm, raw.raw_payload)
        db.add(norm)
        await db.flush()
        result = await resolve_record(norm.id, db)
        await db.commit()
        return {
            "status": "resolved",
            "record_id": result.record_id,
            "decision": result.decision,
            "confidence": result.confidence,
            "ubid": result.ubid,
        }


async def _run_matching_batch(limit: int) -> dict:
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(NormalizedRecord.id)
            .outerjoin(
                RecordLink,
                and_(
                    RecordLink.raw_record_id == NormalizedRecord.raw_record_id,
                    RecordLink.unlinked_at.is_(None),
                ),
            )
            .where(RecordLink.id.is_(None))
            .order_by(NormalizedRecord.normalized_at.asc())
            .limit(limit)
        )
        ids = [row[0] for row in rows.fetchall()]
        results = []
        for norm_id in ids:
            result = await resolve_record(norm_id, db)
            results.append({"record_id": result.record_id, "decision": result.decision, "ubid": result.ubid})
        await db.commit()
        return {"processed": len(results), "results": results}


@celery_app.task(name="ubid.normalize_and_resolve")
def normalize_and_resolve(raw_record_id: str) -> dict:
    return asyncio.run(_normalize_and_resolve(raw_record_id))


@celery_app.task(name="ubid.run_matching_batch")
def run_matching_batch(limit: int = 100) -> dict:
    return asyncio.run(_run_matching_batch(limit))
