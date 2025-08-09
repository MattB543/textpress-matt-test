from __future__ import annotations

import os
from pathlib import Path
import signal
from typing import NamedTuple

from kash.utils.common.url import Url, is_url
# Windows compatibility: ensure SIGUSR1 exists for kash's logger import paths
if not hasattr(signal, "SIGUSR1"):
    try:
        signal.SIGUSR1 = signal.SIGTERM  # type: ignore[attr-defined]
    except Exception:
        pass

try:
    from textpress.actions.textpress_format import textpress_format
    from kash.exec import prepare_action_input, kash_runtime
    from kash.config.setup import kash_setup
    from kash.model import Format
    USE_TEXTPRESS = True
except Exception:
    # Fallback: lightweight pipeline without kash/textpress (avoids heavy GPU deps on DO buildpack)
    from pathlib import Path
    from typing import NamedTuple
    import markdown2
    from jinja2 import Environment, BaseLoader

    USE_TEXTPRESS = False

    class SimpleResult(NamedTuple):
        html: str
        markdown: str
        source_type: str

    SIMPLE_TEMPLATE = """
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{{ title }}</title>
        <style>body{font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,Helvetica,Arial;max-width:48rem;margin:2rem auto;padding:0 1rem;}</style>
      </head>
      <body>
        {{ body|safe }}
      </body>
    </html>
    """

    def simple_format_markdown(md: str) -> SimpleResult:
        html_body = markdown2.markdown(md, extras=["fenced-code-blocks", "tables", "footnotes"])  # type: ignore
        env = Environment(loader=BaseLoader())
        tpl = env.from_string(SIMPLE_TEMPLATE)
        html = tpl.render(title="Textpress", body=html_body)
        return SimpleResult(html=html, markdown=md, source_type="markdown")


class ConvertResult(NamedTuple):
    html: str
    markdown: str | None
    source_type: str


async def convert_and_render(input_path_or_url: Path | str) -> ConvertResult:
    """
    Convert input to Markdown and render HTML via Textpress template.
    Returns HTML and Markdown (if available).
    """
    # Prepare action input (accepts Url or Path)
    src = Url(str(input_path_or_url)) if isinstance(input_path_or_url, str) and is_url(str(input_path_or_url)) else Path(input_path_or_url)  # type: ignore[arg-type]

    if USE_TEXTPRESS:
        # Ensure kash runtime workspace is available for actions
        ws_root = Path(os.environ.get("WORK_ROOT", "./textpress")).resolve()
        ws_path = ws_root / "workspace"
        ws_path.mkdir(parents=True, exist_ok=True)

        # Initialize kash (lightweight) then run within a workspace runtime
        kash_setup(rich_logging=False, kash_ws_root=ws_root, console_log_level="warning")
        with kash_runtime(ws_path, rerun=False, refetch=False):
            action_input = prepare_action_input(src)
            result = textpress_format(action_input)

        md_item = result.get_by_format(Format.markdown, Format.md_html)
        html_item = result.get_by_format(Format.html)

        html = html_item.body or ""
        markdown = md_item.body if md_item.format in {Format.markdown, Format.md_html} else None

        source_type = (
            "url" if is_url(str(input_path_or_url)) else Path(input_path_or_url).suffix.lower().lstrip(".")
        )
        return ConvertResult(html=html, markdown=markdown, source_type=source_type or "unknown")
    else:
        # Fallback: treat URL as unsupported, otherwise parse text/markdown from file
        if isinstance(input_path_or_url, str) and is_url(str(input_path_or_url)):
            raise ValueError("URL inputs require full textpress stack; not available in fallback mode")
        p = Path(input_path_or_url)
        md = p.read_text(encoding="utf-8", errors="ignore")
        result = simple_format_markdown(md)
        return ConvertResult(html=result.html, markdown=result.markdown, source_type=result.source_type)


