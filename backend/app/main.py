from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import boto3
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
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

app = FastAPI(title="Textpress Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

meta_store: Optional[MetaStore] = make_meta_store()


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/api/convert", response_model=ConvertResponse)
async def api_convert(
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    url: str | None = Form(default=None),
):
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
        with open(p, "wb") as f:
            f.write(await file.read())
        input_path = p
    elif text and text.strip():
        p = temp_dir / "input.md"
        p.write_text(text)
        input_path = p
    else:
        input_path = (url or "").strip()

    # Render HTML and (optionally) Markdown
    try:
        result = await convert_and_render(input_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Conversion failed") from e

    # Generate stable random id
    try:
        uid = uuid.uuid7().hex  # type: ignore[attr-defined]
    except Exception:
        uid = uuid.uuid4().hex
    # Persist to Postgres
    if meta_store is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    try:
        meta_store.create_document(uid=uid, source_type=result.source_type, html_body=result.html, md_body=result.markdown)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Failed to save document") from e

    public_url = f"{get_public_base_url()}/d/{uid}.html"
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


