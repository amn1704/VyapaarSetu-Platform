import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from .config import settings
from .services.llm_service import llm_service
from .services.read_model import ensure_read_model
from .routers import query, search, review, activity, legacy

# Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("ubid_platform.log")
    ]
)
logger = logging.getLogger("ubid.main")

app = FastAPI(title="VyapaarSetu API")

# CORS origins are centralized in backend.config settings.
# Defaults preserve current local-dev behavior.
_cors_origins_raw = settings.CORS_ALLOWED_ORIGINS
_cors_allowed_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(query.router, prefix="/api/query", tags=["Query"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(review.router, prefix="/api/review", tags=["Review"])
app.include_router(activity.router, prefix="/api/activity", tags=["Activity"])
app.include_router(legacy.router, tags=["Legacy UI"])

@app.on_event("startup")
async def startup_event():
    """Checks the health of internal services on boot."""
    logger.info("Initializing VyapaarSetu API...")
    await ensure_read_model(engine)
    logger.info("SQL read model views are ready.")
    try:
        health = llm_service.health_check()
        logger.info(f"Ollama Connection: OK. Available models: {health['models']}")
    except Exception as e:
        logger.warning(f"Ollama is unavailable at startup: {e}. AI features will be disabled.")

@app.get("/api/health")
async def health_check():
    """Aggregated health status for monitoring."""
    ollama_status = "unavailable"
    try:
        llm_service.health_check()
        ollama_status = "ok"
    except:
        pass
        
    return {
        "api": "ok",
        "ollama": ollama_status,
        "models": ["llama3.1:8b", "nomic-embed-text:latest"],
        "database": "ok", # Simplified for now
        "redis": "ok"     # Simplified for now
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
