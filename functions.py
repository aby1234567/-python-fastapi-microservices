"""
HTML -> PDF conversion functions.

This module intentionally holds no FastAPI() app instance and no route
decorators - only the endpoint functions, their Pydantic request/response
models, and the internal helpers they need. Wire them into app.py with
app.add_api_route(), e.g.:

    from functions import (
        health,
        convert,
        HealthResponse,
    )
    from fastapi.responses import FileResponse

    app.add_api_route(
        "/pdf/health", health, methods=["GET"],
        response_model=HealthResponse, tags=["pdf"],
    )
    app.add_api_route(
        "/pdf/convert", convert, methods=["POST"],
        response_class=FileResponse, tags=["pdf"],
    )

Every route requires an `Authorization: Bearer <token>` header, checked
against the SECURITY_TOKEN environment variable via the verify_token
dependency defined below.

Preserves the original script's key rendering details:
  - Fixed 1280x900 viewport so layout doesn't depend on Playwright defaults
  - emulate_media("screen") BEFORE navigation, so the layout used to measure
    scrollWidth/scrollHeight matches the layout used later by page.pdf()
    (page.pdf() defaults to "print" media; measuring under a different media
    than you print under can stretch already-rendered Chart.js canvases)
  - A short settle delay after load so Chart.js animations finish before
    dimensions are measured / the PDF is captured
  - PDF page size set to the measured content width/height (single "page"
    output rather than a paginated multi-page PDF)
"""

import asyncio
import concurrent.futures
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from dotenv import get_key
from fastapi import Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright

from logger_setup import logger

VIEWPORT = {"width": 1280, "height": 900}
CHART_SETTLE_MS = 1000  # let Chart.js finish its initial draw/animation

# On Windows, Playwright needs to launch Chromium as a subprocess, which
# only works on the ProactorEventLoop - a SelectorEventLoop raises
# `NotImplementedError` from `subprocess_exec`. Setting the event loop
# policy at import time isn't reliable here: Uvicorn (or another import)
# can end up creating/using a Selector loop regardless of the policy set
# beforehand. Instead, every Playwright render runs in its own short-lived
# thread with a brand-new event loop (Proactor on Windows), fully decoupled
# from whatever loop Uvicorn is using for the request - see
# `_render_html_to_pdf_isolated` below.
_pdf_render_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="pdf-render"
)


def _run_coro_in_new_loop(coro):
    """Run a coroutine to completion on a fresh event loop in the current thread."""
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()



# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #

security = HTTPBearer()
security_token = get_key(".env", "SECURITY_TOKEN")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> None:
    """Require a valid `Authorization: Bearer <token>` header on every route below."""
    if credentials.scheme != "Bearer" or credentials.credentials != security_token:
        logger.warning("Rejected request: invalid or missing bearer token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# --------------------------------------------------------------------------- #
# Pydantic models
# --------------------------------------------------------------------------- #

class HealthResponse(BaseModel):
    """Liveness check response."""

    status: str = Field(..., description="Service status.", examples=["ok"])


# --------------------------------------------------------------------------- #
# Internal helpers (not registered as routes)
# --------------------------------------------------------------------------- #

async def _render_html_to_pdf(source_url: str, pdf_path: Path) -> None:
    """
    Core conversion routine. `source_url` must be something Playwright's
    page.goto() accepts: an http(s) URL or a file:// URL.
    """
    logger.debug("Launching browser for source=%s viewport=%s", source_url, VIEWPORT)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport=VIEWPORT)

        # Force "screen" media BEFORE navigating so the layout used to measure
        # scrollWidth/scrollHeight is the same layout page.pdf() will use later.
        await page.emulate_media(media="screen")

        try:
            await page.goto(source_url, wait_until="networkidle", timeout=30000)
        except Exception as exc:
            await browser.close()
            logger.error("Failed to load HTML source=%s: %s", source_url, exc)
            raise HTTPException(status_code=400, detail=f"Failed to load HTML source: {exc}")

        # Let Chart.js finish its initial draw/animation before measuring/snapshotting.
        await page.wait_for_timeout(CHART_SETTLE_MS)

        dimensions = await page.evaluate(
            """
            () => {
                const body = document.body;
                const html = document.documentElement;
                return {
                    width: Math.max(body.scrollWidth, html.scrollWidth),
                    height: Math.max(body.scrollHeight, html.scrollHeight)
                }
            }
            """
        )
        logger.debug("Measured content dimensions for %s: %s", source_url, dimensions)

        try:
            await page.pdf(
                path=str(pdf_path),
                width=f"{dimensions['width']}px",
                height=f"{dimensions['height']}px",
                print_background=True,
            )
        except Exception as exc:
            await browser.close()
            logger.critical("PDF capture failed for source=%s: %s", source_url, exc)
            raise HTTPException(status_code=500, detail=f"PDF capture failed: {exc}")

        await browser.close()
        logger.info("Rendered PDF for source=%s -> %s", source_url, pdf_path)


def _to_file_url(local_path: Path) -> str:
    """Turn a local filesystem path into a file:// URL Playwright can navigate to."""
    return local_path.resolve().as_uri()


async def _render_html_to_pdf_isolated(source_url: str, pdf_path: Path) -> None:
    """
    Run `_render_html_to_pdf` on its own thread + event loop (see
    `_run_coro_in_new_loop`), so it never depends on Uvicorn's main loop type.
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        _pdf_render_executor,
        _run_coro_in_new_loop,
        _render_html_to_pdf(source_url, pdf_path),
    )


async def _convert_html_bytes_to_pdf_response(html_bytes: bytes, out_stem: str) -> FileResponse:
    """Shared logic: write HTML bytes to a temp file, render to PDF, return as a response."""
    work_id = uuid.uuid4().hex
    logger.info("Starting conversion work_id=%s out_stem=%s size_bytes=%d", work_id, out_stem, len(html_bytes))
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        html_path = tmp_dir_path / f"{work_id}.html"
        pdf_path = tmp_dir_path / f"{work_id}.pdf"

        html_path.write_bytes(html_bytes)

        await _render_html_to_pdf_isolated(_to_file_url(html_path), pdf_path)

        if not pdf_path.exists():
            logger.error("PDF not found after render, work_id=%s", work_id)
            raise HTTPException(status_code=500, detail="PDF generation failed")

        # Copy out of the temp dir before it's cleaned up, so FileResponse can stream it
        final_pdf = Path(tempfile.gettempdir()) / f"{work_id}.pdf"
        final_pdf.write_bytes(pdf_path.read_bytes())

    logger.info("Conversion complete work_id=%s -> %s", work_id, final_pdf)
    return FileResponse(
        path=str(final_pdf),
        media_type="application/pdf",
        filename=f"{out_stem}_pdf.pdf",
    )


# --------------------------------------------------------------------------- #
# Route functions - register these with app.add_api_route()
# --------------------------------------------------------------------------- #

async def health(_: None = Depends(verify_token)) -> HealthResponse:
    """Basic liveness check for the HTML-to-PDF service."""
    logger.debug("Health check hit")
    return HealthResponse(status="ok")


async def convert(
    file: Optional[UploadFile] = File(
        default=None,
        description="An .html or .htm file to convert. Mutually exclusive with 'html'.",
    ),
    html: Optional[str] = Form(
        default=None,
        description="Raw HTML text to convert. Mutually exclusive with 'file'.",
    ),
    _: None = Depends(verify_token),
) -> FileResponse:
    """
    Convert HTML to a PDF.

    Accepts exactly one of, via multipart/form-data:
    - **file**: an uploaded `.html`/`.htm` file
    - **html**: a raw HTML string in a form field

    Note: this endpoint expects multipart/form-data, not a JSON body -
    even for the raw-string case, send `html` as a form field.

    Returns the rendered PDF as a downloadable file.
    """
    if file is not None and html is not None:
        logger.warning("Rejected /convert request: both 'file' and 'html' provided")
        raise HTTPException(status_code=400, detail="Provide either 'file' or 'html', not both")

    if file is not None:
        if not file.filename.lower().endswith((".html", ".htm")):
            logger.warning("Rejected /convert request: bad extension filename=%s", file.filename)
            raise HTTPException(status_code=400, detail="File must be .html or .htm")
        html_bytes = await file.read()
        out_stem = Path(file.filename).stem
        logger.info("Received file upload filename=%s", file.filename)
        return await _convert_html_bytes_to_pdf_response(html_bytes, out_stem)

    if html is not None:
        if not html.strip():
            logger.warning("Rejected /convert request: empty 'html' form field")
            raise HTTPException(status_code=400, detail="'html' field is empty")
        logger.info("Received raw HTML via multipart form field")
        return await _convert_html_bytes_to_pdf_response(html.encode("utf-8"), "report")

    logger.warning("Rejected /convert request: neither 'file' nor 'html' provided")
    raise HTTPException(status_code=400, detail="Provide either a 'file' upload or an 'html' form field")