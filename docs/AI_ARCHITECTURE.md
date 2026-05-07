# Karnataka UBID AI Architecture

## Runtime

All AI inference is local through Ollama:

- `llama3.1:8b`: text-to-SQL, activity explanations, reviewer summaries, reports
- `nomic-embed-text`: business name, address, and combined identity embeddings

No hosted LLM or external AI API is used.

## Folder Structure

```text
backend/
  main.py                         # FastAPI endpoints and startup DDL
  models.py                       # SQLAlchemy ORM, pgvector columns
  worker.py                       # Celery background AI jobs
  services/
    entity_resolution_service.py  # embedding-first matching engine
    embedding_service.py          # local Ollama embedding client
    llm_service.py                # local Ollama LLM + SQL safety
    activity_service.py           # deterministic activity classifier
    review_service.py             # reviewer context/training records
    event_bus.py                  # optional Redpanda/Kafka publisher
    normalization.py              # deterministic normalization helpers
    matching_service.py           # fallback explainability helpers
    scoring.py                    # deprecated fallback weighted scorer
    blocking.py                   # deprecated fallback blocking
```

## Entity Resolution Flow

1. Normalize name, address, GSTIN, PAN, proprietor.
2. Generate `name_embedding`, `address_embedding`, and `business_embedding`.
3. Search nearest records with pgvector cosine similarity on `business_embedding`.
4. Route by semantic similarity:
   - `>= 0.92`: auto match
   - `0.75-0.91`: reviewer queue
   - `< 0.75`: new UBID
5. Store evidence JSON in `scored_pairs`, `review_queue`, and `audit_logs`.

Example match response:

```json
{
  "status": "matching_complete",
  "processed": 1,
  "result": {
    "decision": "review_queue",
    "confidence": 0.83,
    "ubid": null,
    "evidence": {
      "semantic_similarity": 0.83,
      "pan_match": false,
      "address_overlap": 0.71,
      "matched_tokens": ["abc", "textiles"],
      "primary_engine": "pgvector_cosine_similarity",
      "embedding_model": "nomic-embed-text",
      "llm_used_for_matching": false
    }
  }
}
```

## Production Endpoints

- `POST /api/ingest`
- `POST /api/match/run`
- `POST /api/match/reverse`
- `GET /api/review/pending`
- `POST /api/review/decision`
- `GET /api/business/{ubid_code}`
- `POST /api/activity/classify`
- `POST /api/query`

## Background Jobs

Celery tasks:

- `ubid.normalize_and_resolve`
- `ubid.run_matching_batch`

Docker Compose includes Redis, Celery worker, and Redpanda.
