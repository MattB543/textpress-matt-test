from __future__ import annotations

# pyright: reportMissingImports=false

import asyncio
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Optional, List

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


class CombineResponse(BaseModel):
    id: str
    public_url: str
    component_ids: List[str]
    component_urls: List[str]


def _escape_html(text: str) -> str:
    text = text or ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def generate_tab_buttons(doc_ids: list[str], titles: list[str]) -> str:
    buttons: list[str] = []
    for i, (doc_id, title) in enumerate(zip(doc_ids, titles)):
        safe_title = _escape_html(title)
        active_class = " active" if i == 0 else ""
        buttons.append(
            f'<button class="tab-btn{active_class}" data-doc-id="{doc_id}" aria-selected="{str(i==0).lower()}">{safe_title}</button>'
        )
    return "\n".join(buttons)


def generate_fallback_links(doc_ids: list[str], titles: list[str]) -> str:
    items: list[str] = []
    for doc_id, title in zip(doc_ids, titles):
        safe_title = _escape_html(title)
        items.append(f'<div><a href="/d/{doc_id}.html" target="_blank" rel="noreferrer">{safe_title}</a></div>')
    return "\n".join(items)


def generate_tab_switching_js(doc_ids: list[str]) -> str:
    # JS function implementing tab switching and scroll position persistence
    return f"""
function initializeTabs() {{
  const tabs = document.querySelectorAll('.tab-btn');
  const frame = document.getElementById('report-frame');
  const scrollPositions = {{}};
  tabs.forEach((tab, index) => {{
    tab.addEventListener('click', () => {{
      const currentDoc = frame.getAttribute('data-current-doc');
      if (currentDoc && frame.contentWindow) {{
        scrollPositions[currentDoc] = frame.contentWindow.scrollY || 0;
      }}
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const docId = tab.getAttribute('data-doc-id');
      if (!docId) return;
      frame.src = '/d/' + docId + '.html';
      frame.setAttribute('data-current-doc', docId);
      frame.onload = () => {{
        const pos = scrollPositions[docId] || 0;
        try {{
          if (frame.contentWindow) frame.contentWindow.scrollTo(0, pos);
        }} catch (e) {{}}
      }};
    }});
  }});
  document.addEventListener('keypress', (e) => {{
    if (e.key >= '1' && e.key <= '{len(doc_ids)}') {{
      const index = parseInt(e.key, 10) - 1;
      tabs[index] && tabs[index].dispatchEvent(new Event('click'));
    }}
  }});
}}
document.addEventListener('DOMContentLoaded', initializeTabs);
"""


def generate_combined_template(doc_ids: list[str], titles: list[str], combined_title: str) -> str:
    titles = titles or ["Report 1", "Report 2", "Report 3"]
    safe_combined_title = _escape_html(combined_title or "Combined Research Report")
    nav_buttons = generate_tab_buttons(doc_ids, titles)
    fallback_links = generate_fallback_links(doc_ids, titles)
    js = generate_tab_switching_js(doc_ids)
    first_src = f"/d/{doc_ids[0]}.html" if doc_ids else "about:blank"
    template = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{safe_combined_title}</title>
  <style>
    body {{ margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Helvetica Neue, Arial, \"Apple Color Emoji\", \"Segoe UI Emoji\"; }}
    .textpress-header {{ background: #0E0E10; color: #fff; padding: 20px; }}
    .textpress-header .inner {{ max-width: 980px; margin: 0 auto; }}
    .report-tabs {{ display: flex; gap: 8px; padding: 10px; border-bottom: 1px solid #e5e7eb; background: #f8fafc; position: sticky; top: 0; z-index: 10; }}
    .report-tabs .tab-btn {{ appearance: none; border: 1px solid #cbd5e1; background: white; padding: 8px 12px; border-radius: 8px; cursor: pointer; font-weight: 600; color: #0f172a; }}
    .report-tabs .tab-btn.active {{ background: #0f172a; color: white; border-color: #0f172a; }}
    .report-frame {{ width: 100%; height: calc(100vh - 120px); border: none; display: block; }}
    .fallback-links {{ max-width: 980px; margin: 24px auto; }}
  </style>
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\" />
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin />
  <link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap\" rel=\"stylesheet\" />
  <script>
  {js}
  </script>
  <noscript>
    <style>.report-frame {{ display: none; }}</style>
  </noscript>
</head>
<body>
  <header class=\"textpress-header\">
    <div class=\"inner\">
      <h1 style=\"margin:0\">{safe_combined_title}</h1>
    </div>
  </header>
  <nav class=\"report-tabs\" role=\"tablist\" aria-label=\"Combined reports\">
    {nav_buttons}
  </nav>
  <main>
    <iframe id=\"report-frame\" class=\"report-frame\" src=\"{first_src}\" data-current-doc=\"{doc_ids[0]}\"></iframe>
    <noscript>
      <div class=\"fallback-links\">
        {fallback_links}
      </div>
    </noscript>
  </main>
</body>
</html>
"""
    return template


@app.post("/api/combine", response_model=CombineResponse)
async def api_combine(
    request: Request,
    doc_ids: List[str] = Form(...),
    titles: List[str] | None = Form(default=None),
    combined_title: str = Form(default="Combined Research Report"),
):
    # Basic validation
    if meta_store is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    if not doc_ids or len(doc_ids) != 3:
        raise HTTPException(status_code=400, detail="Provide exactly 3 doc_ids")

    # Validate docs exist
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from .meta import Base, Document

        engine = create_engine(meta_store.engine_url)
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            for doc_id in doc_ids:
                doc = session.get(Document, doc_id)
                if not doc:
                    raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("DB validation error")
        raise HTTPException(status_code=500, detail=str(e))

    # Normalize titles length to match doc_ids
    safe_titles = titles or ["Report 1", "Report 2", "Report 3"]
    if titles and len(titles) != len(doc_ids):
        defaults = ["Report 1", "Report 2", "Report 3"]
        safe_titles = (titles + defaults)[: len(doc_ids)]

    combined_html = generate_combined_template(
        doc_ids=doc_ids,
        titles=safe_titles,
        combined_title=combined_title,
    )

    combined_id = uuid.uuid4().hex
    try:
        meta_store.create_document(
            uid=combined_id,
            source_type="combined",
            html_body=combined_html,
            md_body=None,
            doc_metadata={
                "type": "combined",
                "component_ids": doc_ids,
                "component_titles": safe_titles,
                "combined_title": combined_title,
            },
        )
    except Exception as e:
        logger.exception("Failed to save combined document")
        raise HTTPException(status_code=500, detail="Failed to save document")

    public_url = f"{get_public_base_url()}/d/{combined_id}.html"
    component_urls = [f"{get_public_base_url()}/d/{doc_id}.html" for doc_id in doc_ids]
    return CombineResponse(
        id=combined_id,
        public_url=public_url,
        component_ids=doc_ids,
        component_urls=component_urls,
    )