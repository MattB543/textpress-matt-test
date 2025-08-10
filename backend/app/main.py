from __future__ import annotations

# pyright: reportMissingImports=false

import asyncio
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from time import perf_counter

from .meta import MetaStore, make_meta_store


class ConvertResponse(BaseModel):
    id: str
    public_url: str


def get_public_base_url() -> str:
    base = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")
    return base.rstrip("/")


load_dotenv()

# Configure logger
logger = logging.getLogger("textpress.backend")
if not logger.handlers:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

app = FastAPI(title="Textpress Backend", version="0.1.0")

# CORS setup
cors_env = os.environ.get("CORS_ALLOW_ORIGINS", "*").strip()
allow_origins = ["*"] if cors_env == "*" or cors_env == "" else [o.strip() for o in cors_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

meta_store: Optional[MetaStore] = make_meta_store()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = perf_counter()
    origin = request.headers.get("origin")
    content_length = request.headers.get("content-length")
    logger.info(
        "HTTP start method=%s path=%s origin=%s content_length=%s",
        request.method,
        request.url.path,
        origin,
        content_length,
    )
    try:
        response = await call_next(request)
        return response
    except Exception:
        # Ensure all unhandled exceptions are logged with traceback
        logger.exception("Unhandled exception for %s %s", request.method, request.url.path)
        raise
    finally:
        duration_ms = int((perf_counter() - start) * 1000)
        status = getattr(locals().get("response", None), "status_code", None)
        logger.info(
            "HTTP end method=%s path=%s status=%s duration_ms=%s",
            request.method,
            request.url.path,
            status,
            duration_ms,
        )


@app.exception_handler(HTTPException)
async def http_exception_logger(request: Request, exc: HTTPException):  # pyright: ignore[reportUnusedParameter]
    logger.warning(
        "HTTPException method=%s path=%s status=%s detail=%s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_logger(request: Request, exc: Exception):  # pyright: ignore[reportUnusedParameter]
    logger.exception(
        "Unhandled error method=%s path=%s: %s",
        request.method,
        request.url.path,
        str(exc),
    )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.get("/healthz")
def healthz() -> dict:
    db_ok = None
    if meta_store is not None:
        try:
            meta_store.test_connection()
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
    add_title: bool = Form(default=False),
    add_classes: str | None = Form(default=None),
    no_minify: bool = Form(default=False),
):
    logger.info(
        "Convert start origin=%s file=%s text_len=%s url=%s add_title=%s add_classes=%s no_minify=%s",
        request.headers.get("origin"),
        getattr(file, "filename", None),
        (len(text) if text else 0),
        (url or None),
        add_title,
        add_classes,
        no_minify,
    )

    if not (file or (text and text.strip()) or (url and url.strip())):
        raise HTTPException(status_code=400, detail="Provide file or text or url")

    # Process with CLI
    from .process_cli import process_with_cli

    try:
        result = await process_with_cli(
            file=file,
            text=text,
            url=url,
            add_classes=add_classes,
            no_minify=no_minify
        )
    except Exception as e:
        logger.exception("Conversion error")
        raise HTTPException(status_code=500, detail=str(e))
    logger.info(
        "Convert CLI done source_type=%s html_len=%s md_len=%s",
        result.get("source_type"),
        (len(result.get("html", ""))),
        (len(result.get("markdown")) if result.get("markdown") else 0),
    )

    # Generate ID and persist
    uid = uuid.uuid4().hex

    if meta_store is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        logger.info("Saving document uid=%s to database", uid)
        meta_store.create_document(
            uid=uid,
            source_type=result["source_type"],
            html_body=result["html"],
            md_body=result.get("markdown")
        )
    except Exception as e:
        logger.exception("Failed to save document")
        raise HTTPException(status_code=500, detail="Failed to save document")
    logger.info("Saved document uid=%s", uid)

    public_url = f"{get_public_base_url()}/d/{uid}.html"
    return ConvertResponse(id=uid, public_url=public_url)


@app.get("/d/{uid}.html")
def serve_html(uid: str):
    if meta_store is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from .meta import Base, Document

    engine = create_engine(meta_store.engine_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        doc = session.get(Document, uid)
        if not doc or not doc.html_body:
            logger.warning("HTML not found uid=%s", uid)
            raise HTTPException(status_code=404, detail="Not found")
        logger.info("Serve HTML uid=%s size=%s", uid, len(doc.html_body or ""))
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
            logger.warning("MD not found uid=%s", uid)
            raise HTTPException(status_code=404, detail="Not found")
        logger.info("Serve MD uid=%s size=%s", uid, len(doc.md_body or ""))
        return Response(content=doc.md_body, media_type="text/markdown; charset=utf-8")


