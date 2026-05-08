from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from ..config import settings
from ..database import get_db
from ..services.llm_service import llm_service

router = APIRouter()

class ActivityRequest(BaseModel):
    ubid: str

@router.post("/explain")
async def explain_activity(request: ActivityRequest, db: AsyncSession = Depends(get_db)):
    """
    Provides a plain-English explanation of a business's current status 
    based on their event timeline.
    """
    if not settings.ENABLE_LLM:
        raise HTTPException(status_code=503, detail="AI activity explanations are disabled. Set ENABLE_LLM=true to use Ollama locally.")

    # 1. Fetch events from PostgreSQL
    event_sql = "SELECT event_type, event_date, event_outcome FROM activity_events WHERE ubid = :ubid ORDER BY event_date DESC"
    registry_sql = "SELECT status FROM ubid_registry WHERE ubid = :ubid"
    
    try:
        registry_res = await db.execute(text(registry_sql), {"ubid": request.ubid})
        status_row = registry_res.fetchone()
        if not status_row:
             raise HTTPException(status_code=404, detail="UBID not found")
        
        status = status_row.status
        
        event_res = await db.execute(text(event_sql), {"ubid": request.ubid})
        events = [dict(row._mapping) for row in event_res.all()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database lookup failed: {e}")

    # 2. Build activity_dict (safe, no PII)
    activity_dict = {
        "status": status,
        "events": events
    }

    # 3. Call LLM for explanation
    try:
        explanation_raw = await llm_service.explain_activity(activity_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM failure: {e}")

    # Parse structured output
    # Expected format:
    # Status: [Active / Dormant / Closed]
    # Explanation: [2-3 sentences]
    # Last significant event: [type] — [relative time]
    
    lines = explanation_raw.split("\n")
    explanation_text = explanation_raw
    last_event = "Unknown"
    
    for line in lines:
        if line.startswith("Explanation:"):
            explanation_text = line.replace("Explanation:", "").strip()
        if line.startswith("Last significant event:"):
            last_event = line.replace("Last significant event:", "").strip()

    return {
        "ubid": request.ubid,
        "status": status,
        "explanation": explanation_text,
        "last_event": last_event
    }
