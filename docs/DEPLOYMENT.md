# Deployment Notes

## Frontend (Vercel)

- Root config uses `vercel.json` to build from `frontend/`.
- Build output: `frontend/dist`.
- SPA routing fallback is enabled via rewrite to `/index.html`.

Environment variables:

- `VITE_API_BASE_URL` (optional): set when API is hosted on a different origin.
  - Example: `https://api.vyapaarsetu.in`

## Backend

- Deploy backend separately (FastAPI + database).
- Ensure these are set:
  - `DATABASE_URL`
  - `JWT_SECRET_KEY`
  - `CORS_ALLOWED_ORIGINS`
  - `OLLAMA_HOST` (if AI features are enabled)

## Contract Checklist

- Frontend should only call documented `/api/...` endpoints.
- Keep response compatibility for record IDs (`id` + `source_record_id`) during transition.
- Validate review actions with reviewer identity (`reviewerId` or `X-Reviewer-Id`).
