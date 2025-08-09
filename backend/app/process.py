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

from textpress.actions.textpress_format import textpress_format
from kash.exec import prepare_action_input, kash_runtime
from kash.config.setup import kash_setup
from kash.config.logger import CustomLogger, get_logger
from kash.model import Format


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

    # Basic source type classification for metadata
    source_type = (
        "url" if is_url(str(input_path_or_url)) else Path(input_path_or_url).suffix.lower().lstrip(".")
    )

    return ConvertResult(html=html, markdown=markdown, source_type=source_type or "unknown")


