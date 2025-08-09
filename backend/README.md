# Textpress Backend (FastAPI)

Minimal hosted MVP backend service.

Endpoints:

- POST `/api/convert` — multipart: accepts `file` OR `text` OR `url`; returns `{ id, public_url }`.
- GET `/d/{id}.html` — serves published HTML directly from Postgres.
- GET `/d/{id}.md` — serves Markdown (if available) from Postgres.
- POST `/api/delete` (optional) — requires signed token (not implemented in MVP).
- GET `/healthz`.

Environment variables:

- `DATABASE_URL` (Postgres), e.g. `postgresql+psycopg2://user:pass@host:5432/db`.
- `PUBLIC_BASE_URL` (e.g. `https://textpress.md`) used in API responses for link construction.
- `MAX_UPLOAD_MB` (default 15).

Run locally:

```sh
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

DB migrations: not required for MVP (single table auto-created). `DATABASE_URL` is required for this Postgres-only variant.
