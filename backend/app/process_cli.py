# app/process_cli.py - FIXED ARGUMENT ORDER
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
    Works on Windows by using asyncio.to_thread with regular subprocess.
    """
    
    # Use context manager for automatic cleanup
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
        
        # Build the command - FIXED ORDER: global args before subcommand
        cmd = [
            "uv", "run", "textpress",
            "--work_root", str(temp_path),  # Global arg BEFORE subcommand
            "format",  # Subcommand
            input_arg  # Subcommand argument
        ]
        
        # Add subcommand-specific options
        if add_classes:
            cmd.extend(["--add_classes", add_classes])
        if no_minify:
            cmd.append("--no_minify")
        
        logger.info("Running command: %s", " ".join(cmd))
        
        # Define a synchronous function to run the subprocess
        def run_subprocess():
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    cwd=os.getcwd(),
                    env={**os.environ},
                    timeout=30  # 30 second timeout
                )
                return result
            except subprocess.TimeoutExpired as e:
                logger.error("Command timed out: %s", e)
                raise RuntimeError(f"Textpress CLI timed out after 30 seconds")
            except FileNotFoundError:
                raise RuntimeError(
                    "textpress CLI not found. Install it with: uv add textpress"
                )
        
        # Run the subprocess in a thread pool (works on Windows!)
        try:
            result = await asyncio.to_thread(run_subprocess)
            
            if result.returncode != 0:
                logger.error("CLI stdout: %s", result.stdout)
                logger.error("CLI stderr: %s", result.stderr)
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise RuntimeError(f"Textpress CLI failed: {error_msg}")
                
            logger.info("CLI stdout: %s", result.stdout[:500])  # Log first 500 chars
            
        except Exception as e:
            logger.exception("Failed to run textpress CLI")
            raise
        
        # The textpress CLI outputs to workspace/docs/
        workspace_dir = temp_path / "workspace"
        
        # Find all HTML and MD files recursively
        html_files = list(workspace_dir.rglob("*.html"))
        md_files = list(workspace_dir.rglob("*.md"))
        
        logger.info(f"Found {len(html_files)} HTML files and {len(md_files)} MD files")
        
        # Log workspace contents for debugging
        if not html_files or not md_files:
            all_files = list(workspace_dir.rglob("*"))
            logger.info(f"Workspace contains {len(all_files)} files total")
            for f in all_files[:20]:  # Log first 20 files
                logger.info(f"  - {f.relative_to(temp_path)}")
        
        if not html_files:
            # Try alternative locations
            html_files = list(temp_path.rglob("*.html"))
            if not html_files:
                all_files = list(temp_path.rglob("*"))
                raise RuntimeError(
                    f"No HTML output generated. Files in temp dir: {[str(f.relative_to(temp_path)) for f in all_files[:30]]}"
                )
        
        # Read the results
        html_content = html_files[0].read_text(encoding='utf-8')
        md_content = md_files[0].read_text(encoding='utf-8') if md_files else None
        
        logger.info(f"Successfully read HTML ({len(html_content)} chars) and MD ({len(md_content) if md_content else 0} chars)")
        
        return {
            "html": html_content,
            "markdown": md_content,
            "source_type": source_type
        }