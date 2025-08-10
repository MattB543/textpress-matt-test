from __future__ import annotations

import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import boto3
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from .meta import MetaStore, make_meta_store
from .process import convert_and_render


class ConvertResponse(BaseModel):
    id: str
    public_url: str


def get_public_base_url() -> str:
    # In Postgres-served MVP, backend serves /d/*; default to backend port for local dev
    base = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")
    return base.rstrip("/")


def max_upload_bytes() -> int:
    mb = int(os.environ.get("MAX_UPLOAD_MB", "15"))
    return mb * 1024 * 1024


load_dotenv()  # Load .env if present for local dev

# Configure logger
logger = logging.getLogger("textpress.backend")
if not logger.handlers:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

app = FastAPI(title="Textpress Backend", version="0.1.0")

cors_env = os.environ.get("CORS_ALLOW_ORIGINS", "*").strip()
allow_origins = ["*"] if cors_env == "*" or cors_env == "" else [o.strip() for o in cors_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("FastAPI app initialized; CORS allow_origins=%s credentials=%s methods=* headers=*", allow_origins, False)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("REQ %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled error for %s %s", request.method, request.url.path)
        raise
    logger.info("RES %s %s -> %s", request.method, request.url.path, getattr(response, "status_code", "?"))
    return response

meta_store: Optional[MetaStore] = make_meta_store()
if meta_store is None:
    logger.warning("Meta store not configured: set DATABASE_URL to enable persistence")
else:
    # Log a safe, redacted version of the DB URL host:port for diagnostics
    try:
        from urllib.parse import urlparse

        u = urlparse(os.environ.get("DATABASE_URL", ""))
        safe_loc = f"{u.hostname}:{u.port}" if u.hostname else "?"
        logger.info("Meta store initialized (db=%s)", safe_loc)
        # Proactively test connection with short timeout
        try:
            meta_store.test_connection()  # type: ignore[attr-defined]
            logger.info("Database connectivity: ok")
        except Exception:
            logger.exception("Database connectivity: FAILED")
    except Exception:
        logger.exception("Error while logging DB diagnostics")


@app.get("/healthz")
def healthz() -> dict:
    db_ok = None
    if meta_store is not None:
        try:
            meta_store.test_connection()  # type: ignore[attr-defined]
            db_ok = True
        except Exception:
            db_ok = False
    return {"ok": True, "db": db_ok}


@app.post("/api/convert", response_model=ConvertResponse)
async def api_convert(
    request: Request,
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    url: str | None = Form(default=None),
):
    logger.info(
        "POST /api/convert from origin=%s ua=%s",
        request.headers.get("origin"),
        request.headers.get("user-agent"),
    )
    logger.info(
        "Incoming payload: file=%s, file_size=%s, text_len=%s, url=%s",
        getattr(file, "filename", None),
        getattr(file, "size", None),  # UploadFile may not have size; kept for visibility
        len(text) if text else 0,
        (url or "").strip()[:200],
    )
    if not (file or (text and text.strip()) or (url and url.strip())):
        raise HTTPException(status_code=400, detail="Provide file or text or url")

    # Validate sizes (text only here; file size should be limited by proxy/server config)
    if text and len(text) > 2_000_000:
        raise HTTPException(status_code=413, detail="Text too long")

    # Prepare input path (either saved file, temp text file, or URL string)
    temp_dir = Path(tempfile.mkdtemp(prefix="tp-"))
    input_path: Path | str

    if file:
        suffix = Path(file.filename or "upload").suffix.lower()
        if suffix not in {".docx", ".md", ".markdown", ".txt"}:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        p = temp_dir / f"upload{suffix}"
        logger.info("Saving uploaded file to %s", p)
        body = await file.read()
        with open(p, "wb") as f:
            f.write(body)
        logger.info("Saved file bytes=%d", len(body))
        input_path = p
    elif text and text.strip():
        p = temp_dir / "input.md"
        logger.info("Writing text input to %s (len=%d)", p, len(text))
        p.write_text(text)
        input_path = p
    else:
        input_path = (url or "").strip()
        logger.info("Processing URL input: %s", (url or "").strip())

    # Render HTML and (optionally) Markdown
    try:
        logger.info("Starting convert_and_render for source=%s", input_path)
        result = await convert_and_render(input_path)
        logger.info(
            "Conversion complete: source_type=%s, html_len=%d, md_len=%s",
            result.source_type,
            len(result.html or ""),
            (len(result.markdown) if result.markdown else None),
        )
    except ValueError as e:
        logger.exception("Conversion validation error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("Unexpected conversion error")
        raise HTTPException(status_code=500, detail="Conversion failed") from e

    # Generate stable random id
    try:
        uid = uuid.uuid7().hex  # type: ignore[attr-defined]
    except Exception:
        uid = uuid.uuid4().hex
    # Persist to Postgres
    if meta_store is None:
        logger.error("DATABASE_URL is not configured; cannot persist document")
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        logger.info("Persisting document uid=%s to database", uid)
        meta_store.create_document(uid=uid, source_type=result.source_type, html_body=result.html, md_body=result.markdown)
        logger.info("Persisted document uid=%s", uid)
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to save document uid=%s", uid)
        raise HTTPException(status_code=500, detail="Failed to save document") from e

    public_url = f"{get_public_base_url()}/d/{uid}.html"
    logger.info("Returning response uid=%s public_url=%s", uid, public_url)
    return ConvertResponse(id=uid, public_url=public_url)


@app.get("/d/{uid}.html")
def serve_html(uid: str):
    if meta_store is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    from fastapi.responses import Response
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from .meta import Base, Document

    engine = create_engine(meta_store.engine_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        doc = session.get(Document, uid)
        if not doc or not doc.html_body:
            raise HTTPException(status_code=404, detail="Not found")
        return Response(content=doc.html_body, media_type="text/html; charset=utf-8")


@app.get("/d/{uid}.md")
def serve_md(uid: str):
    if meta_store is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    from fastapi.responses import Response
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from .meta import Base, Document

    engine = create_engine(meta_store.engine_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        doc = session.get(Document, uid)
        if not doc or doc.md_body is None:
            raise HTTPException(status_code=404, detail="Not found")
        return Response(content=doc.md_body, media_type="text/markdown; charset=utf-8")


