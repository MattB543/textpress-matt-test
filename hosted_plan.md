# Textpress Hosted MVP Plan

Goal: Launch a minimal, clean, web-only Textpress service that lets a user drag-and-drop text or a .docx (initially) and instantly returns a unique URL to a formatted, hosted page. Keep infra simple; avoid a database if possible. Abstract away all CLI details.

## Guiding principles

- Minimal moving parts; prefer “dumb storage + short Python service + static frontend”.
- Fast to ship; defer non-essentials (auth, teams, dashboards).
- No DB if we can avoid it; use object storage keys as the “database”.
- Keep binary surface small; favor a single container with Python + `textpress` library.

## User experience (MVP)

1. User opens `textpress.md` and sees a single drag-and-drop box with a CTA button.
2. User drops `.docx` (or pastes/enters text). Presses “Convert & Publish”.
3. Progress indicator shows “Uploading… Converting… Publishing…”.
4. Returns a unique link like `https://textpress.md/d/<UID>.html` to the hosted page.
5. Page features: nice template, supports light/dark, responsive.

Scope (MVP): `.docx`, `.md`, `.txt`, and URLs. Defer PDF until later (slower, heavier).

## Architecture overview (no-DB version)

- Frontend: Static site (one page), deployed to CDN.
  - Plain HTML + minimal JS or a tiny Vite app. Drag-and-drop, progress, and result link.
- API: Python FastAPI service in a small container (Railway, Fly.io, Render, or AWS ECS/Fargate).
  - Endpoints:
    - `POST /api/convert` (multipart): accepts file OR `text` OR `url`. Returns JSON `{id, public_url}`.
    - `POST /api/delete` (optional): accepts a signed delete token to remove uploads.
    - `GET /healthz`.
  - Processing pipeline:
    - Use `textpress` library directly: `textpress.actions.textpress_format`.
    - For `.docx`, `.md`, `.txt`, and `url` → convert to Markdown → render HTML using bundled template.
    - Minify HTML by default.
  - Storage:
    - Upload final HTML (and optionally the clean Markdown) to S3-compatible storage (AWS S3, Cloudflare R2, or Backblaze B2).
    - Public-read bucket with per-object unique key.
    - Key layout: `d/<uid>.html` and optionally `d/<uid>.md` and any assets.
  - Return the public URL to the client.
- Static hosting/CDN:
  - Serve the frontend and published docs via CDN (CloudFront or Cloudflare). Origin is the object storage bucket.
  - Domain `textpress.md` points to CDN; CDN routes `/api/*` to API service and everything else to the bucket (static assets + published docs).

Notes:

- No database: IDs are random `ULID`/`UUIDv4`, used as object keys; the “manifest” is the bucket itself.
- Optional delete: sign a short-lived token (HMAC with server secret) to authorize delete without accounts.
- Abuse controls: file size limits (e.g., 15 MB), mime allowlist, basic IP rate limiting, and captcha if needed.

## Minimal DB variant (only if needed)

If you later need moderation, analytics, or per-user history, add Postgres (Neon, Supabase, Railway Postgres):

- Table `documents(id, status, created_at, source_type, input_name, html_key, md_key, ip_hash, delete_token_hash)`.
- Keep API behavior identical; just `INSERT` on start and `UPDATE` when uploaded.
- Still store payloads/outputs in object storage; DB is just metadata.

## Detailed data flow

1. Frontend sends multipart `POST /api/convert` with either:
   - `file` (docx/md/txt), OR
   - `text` (string), OR
   - `url` (string)
2. API validates input and size; chooses conversion path.
3. API calls `textpress_format` to produce clean Markdown + HTML. PDF skipped in MVP.
4. API writes `d/<uid>.html` (and optional `d/<uid>.md`) to S3 with `public-read` ACL.
5. API returns `{ id, public_url: https://textpress.md/d/<uid>.html }`.
6. Frontend switches to the success state with a shareable link.

## Security, limits, and quality

- Limits: max upload 15 MB; max text length ~2 MB.
- Types: allow `.docx`, `.md`, `.markdown`, `.txt` (and `url`). Reject unknown types.
- Timeouts: end-to-end request timeout 45–60s; show progress UI.
- Sanitization: HTML generated via trusted template from Markdown; drop raw HTML from user input or sanitize via `bleach` if needed.
- Abuse: soft-rate-limit by IP; optional Captcha/Turnstile if abuse appears.
- Privacy: no indexing header (e.g., `X-Robots-Tag: noindex`) initially if you want ephemeral links; make configurable.

## Hosting choices (pick one stack)

“Simplest path” suggestion:

- Object storage: Cloudflare R2 (simple, inexpensive) or AWS S3 (ubiquitous).
- CDN/Domain: Cloudflare (simple DNS + CDN + SSL) or AWS CloudFront + Route53.
- API compute: Railway or Fly.io (fast to deploy containers with persistent env); or AWS ECS Fargate (more setup).
- Container registry: GitHub Container Registry (GHCR) or Docker Hub.

Why not serverless? Converters (`kash-docs[full]`, `flowmark`) are heavy; cold starts and size limits on Lambda/Workers are painful. A small always-on container is simpler for MVP.

## Implementation steps (checklist)

1. Reuse library

   - Publish `textpress` to PyPI (already in place) and pin version in the API service `pyproject.toml`.
   - In the API, import `textpress.actions.textpress_format` and wire to FastAPI endpoint.

2. API service

   - Scaffold FastAPI app with endpoints: `/healthz`, `POST /api/convert`, optional `POST /api/delete`.
   - Configure env: `STORAGE_BUCKET`, `STORAGE_REGION`, `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `PUBLIC_BASE_URL`, `MAX_UPLOAD_MB`, `DELETE_TOKEN_SECRET`.
   - Implement input validation and size checks.
   - Generate ID with ULID/UUIDv4.
   - Persist results to S3 under `d/<id>.html` and optionally `d/<id>.md`.
   - Return JSON with `public_url`.

3. Storage & CDN

   - Create bucket (R2/S3). Enable public read (via policy or signed URL configuration).
   - Configure CDN:
     - Route `GET /d/*` directly to bucket (static origin).
     - Route `/` (frontend), `/assets/*` to a small static site (could also live in the bucket).
     - Route `/api/*` to the API service origin.

4. Frontend (static)

   - Simple single-page with drag-and-drop + file input + text box + URL input tabs.
   - Show progress (upload, convert, publish) and then the shareable link with “Copy” button.
   - Vanilla JS or minimal React/Vite app. Keep bundle small.

5. Deploy

   - Build container, push to GHCR.
   - Deploy to Railway/Fly.io with env vars.
   - Point Cloudflare/Route53 DNS to CDN; configure routes/origins.

6. Observability

   - Basic JSON logs to stdout; capture in host platform.
   - Add `/healthz` and basic metrics (requests, errors, durations) if platform supports.

7. QA

   - Test `.docx` (Deep Research export), `.md`, `.txt`, and `url` inputs.
   - Verify size limits, timeouts, and error handling messages.
   - Verify mobile UX and dark mode.

8. Launch checklist
   - Landing copy, privacy/ToS pages.
   - 429 handling and clear error messages.
   - Rate limiting (per-IP) and upload caps.
   - Backups/retention policy (e.g., objects expire after 90 days unless pinned—defer if not needed).

## Optional “nice-to-have” (post-MVP)

- PDF support (Marker/MarkItDown) with worker queue.
- Delete link with signed token + one-click removal.
- Minimal auth (email magic link) to let users view their last N posts.
- Editable title/description before publish; social card preview.
- Custom subpaths/aliases instead of UIDs.
- Custom domains for power users.
- Webhooks/embeds.

## API sketch

POST /api/convert

Request (multipart/form-data): one of

- file: <binary>
- text: <string>
- url: <string>

Response (200):

```json
{ "id": "01JABCDEF...", "public_url": "https://textpress.md/d/01JABCDEF.html" }
```

POST /api/delete (optional)

Request JSON: `{ "token": "<signed-token>" }`

Response (200): `{ "ok": true }`

## Sizing and costs (ballpark)

- Storage: R2 or S3, pennies per GB-month (HTML is small; docx inputs not stored long-term in MVP).
- Egress: light; CDN caches.
- Compute: 256–512 MB RAM container should suffice; scale to 1–2 instances.
- Domain + TLS: Cloudflare free/low-cost.

## License considerations

`textpress` is AGPL-3.0-or-later. If you modify and run it as a networked service, ensure compliance by making corresponding source changes available as required by AGPL. Using the unmodified PyPI package is typically simpler for compliance.

---

Bottom line: For the very first MVP, ship a static landing page + one FastAPI container + one object store + one CDN route. No DB. Limit to `.docx`/`.md`/`.txt`/`url`. Return a unique public URL to the formatted page.
