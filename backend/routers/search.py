from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from ..database import get_db
from ..services.embed_service import embed_service
from ..services.pseudonymiser import pseudonymiser

router = APIRouter()

class SemanticSearchRequest(BaseModel):
    name: str
    pin_code: str = None

@router.post("/semantic")
async def semantic_search(request: SemanticSearchRequest, db: AsyncSession = Depends(get_db)):
    """
    Finds business entities based on semantic name similarity using pgvector.
    """
    # 1. Normalise + Pseudonymise (handled inside embed_business_name)
    # 2. Embed
    try:
        query_vec = embed_service.embed_business_name(request.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failure: {e}")

    # 3. Query pgvector for top 10
    # Note: Using <=> operator for cosine distance (1 - cosine similarity)
    search_sql = """
        SELECT e.ubid, e.normalised_name, 
               1 - (e.embedding <=> :query_vec) AS similarity,
               r.business_name, r.status
        FROM ubid_embeddings e
        JOIN ubid_registry r ON e.ubid = r.ubid
        ORDER BY e.embedding <=> :query_vec
        LIMIT 10
    """
    
    try:
        result = await db.execute(text(search_sql), {"query_vec": str(query_vec)})
        matches = []
        for row in result.all():
            sim = float(row.similarity)
            # 4. Filter similarity > 0.75
            if sim > 0.75:
                matches.append({
                    "ubid": row.ubid,
                    "business_name": row.business_name,
                    "similarity": round(sim, 4),
                    "status": row.status
                })
                
        return {"matches": matches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector search failed: {e}")
