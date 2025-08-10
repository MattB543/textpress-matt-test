# app/process_cli.py - FIXED TO RUN AS MODULE
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from fastapi import UploadFile

logger = logging.getLogger("textpress.backend.process_cli")


async def process_with_cli(
    file: UploadFile | None = None,
    text: str | None = None,
    url: str | None = None,
    add_classes: str | None = None,
    no_minify: bool = False
) -> dict[str, Any]:
    """
    Process input using textpress CLI tool via subprocess.
    """
    
    with tempfile.TemporaryDirectory(prefix="tp-") as temp_dir:
        temp_path = Path(temp_dir)
        
        # Prepare input
        if file:
            suffix = Path(file.filename or "upload").suffix.lower()
            if suffix not in {".docx", ".md", ".markdown", ".txt"}:
                raise ValueError(f"Unsupported file type: {suffix}")
            
            input_file = temp_path / f"input{suffix}"
            content = await file.read()
            input_file.write_bytes(content)
            input_arg = str(input_file)
            source_type = suffix.lstrip(".")
            
        elif text and text.strip():
            input_file = temp_path / "input.md"
            input_file.write_text(text, encoding='utf-8')
            input_arg = str(input_file)
            source_type = "text"
            
        elif url and url.strip():
            input_arg = url.strip()
            source_type = "url"
        else:
            raise ValueError("No input provided")
        
        # Build command - run as Python module instead of CLI command
        cmd = [
            "python", "-m", "textpress.cli.cli_main",  # Run as module
            "--work_root", str(temp_path),
            "format",
            input_arg
        ]
        
        if add_classes:
            cmd.extend(["--add_classes", add_classes])
        if no_minify:
            cmd.append("--no_minify")
        
        logger.info("Running command: %s", " ".join(cmd))
        
        # Run the subprocess
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ}
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            
            if proc.returncode != 0:
                error_msg = stderr.decode() if stderr else stdout.decode() if stdout else "Unknown error"
                logger.error("CLI failed: %s", error_msg)
                raise RuntimeError(f"Textpress CLI failed: {error_msg}")
                
        except asyncio.TimeoutError:
            raise RuntimeError("Textpress CLI timed out after 30 seconds")
        except FileNotFoundError:
            raise RuntimeError("Python or textpress module not found")
        
        # Find output files
        workspace_dir = temp_path / "workspace"
        html_files = list(workspace_dir.rglob("*.html"))
        md_files = list(workspace_dir.rglob("*.md"))
        
        if not html_files:
            all_files = list(temp_path.rglob("*"))
            raise RuntimeError(f"No HTML output. Files: {[f.name for f in all_files if f.is_file()]}")
        
        return {
            "html": html_files[0].read_text(encoding='utf-8'),
            "markdown": md_files[0].read_text(encoding='utf-8') if md_files else None,
            "source_type": source_type
        }