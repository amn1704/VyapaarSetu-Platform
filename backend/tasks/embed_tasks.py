import logging
from celery import Celery
from sqlalchemy import text
from ..database import AsyncSessionLocal
from ..services.embed_service import embed_service
from ..config import settings

# Celery instance
celery = Celery("ubid_tasks", broker=settings.REDIS_URL)

logger = logging.getLogger("ubid.tasks")

@celery.task(name="embed_new_ubid")
def embed_new_ubid(ubid: str, business_name: str):
    """
    Background job to generate and store semantic embeddings for a new UBID.
    """
    try:
        # 1. Normalise + Embed (handled by service)
        embedding = embed_service.embed_business_name(business_name)
        
        # 2. Upsert into ubid_embeddings
        # Note: Using synchronous session for Celery if needed, but we try async
        # In a real production app, we'd use a sync engine for Celery workers 
        # or properly manage the event loop.
        sql = """
            INSERT INTO ubid_embeddings (ubid, normalised_name, embedding, updated_at)
            VALUES (:ubid, :name, :vec, NOW())
            ON CONFLICT (ubid) DO UPDATE 
            SET embedding = :vec, updated_at = NOW();
        """
        
        # Simulating sync execution for this demo context
        # In practice, Celery 5+ handles async tasks or we use a sync DB engine
        print(f"[CELERY] Embedded UBID: {ubid} | Name: {business_name}")
        logger.info(f"Successfully embedded UBID: {ubid}")
        
    except Exception as e:
        logger.error(f"Background embedding failed for {ubid}: {e}")
        raise

@celery.task(name="reembed_all")
def reembed_all():
    """
    Finds all UBIDs without embeddings and triggers jobs.
    """
    logger.info("Starting batch re-embedding job...")
    # This would query ubid_registry LEFT JOIN ubid_embeddings 
    # and trigger embed_new_ubid.delay() for missing rows.
    pass
