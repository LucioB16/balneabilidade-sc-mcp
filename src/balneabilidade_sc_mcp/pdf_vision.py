"""Render bulletin PDF pages for a vision-capable client fallback.

The deterministic parser remains the primary source. This module is only used
when the parser cannot produce a trustworthy row set and the caller wants to
let a vision-capable model read the original page images.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ImaInvalidArgument, ImaSchemaError

try:  # pragma: no cover - exercised when the optional renderer is installed
    import pymupdf
except ImportError:  # pragma: no cover
    pymupdf = None  # type: ignore[assignment]


@dataclass(frozen=True)
class RenderedPage:
    page_number: int
    page_count: int
    data: bytes
    mime_type: str
    width: int
    height: int


def pdf_page_count(pdf_bytes: bytes) -> int:
    if pymupdf is None:
        raise ImaSchemaError("PyMuPDF is not installed; PDF page rendering is unavailable")
    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ImaSchemaError("PDF could not be opened for rendering") from exc
    try:
        return int(document.page_count)
    finally:
        document.close()


def render_pdf_page(pdf_bytes: bytes, page_number: int, *, dpi: int = 120) -> RenderedPage:
    if pymupdf is None:
        raise ImaSchemaError("PyMuPDF is not installed; PDF page rendering is unavailable")
    if page_number < 1:
        raise ImaInvalidArgument("page_number must be at least 1")
    dpi = min(200, max(72, dpi))
    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ImaSchemaError("PDF could not be opened for rendering") from exc
    try:
        if page_number > document.page_count:
            raise ImaInvalidArgument(
                f"page_number {page_number} exceeds the bulletin's {document.page_count} pages"
            )
        page = document.load_page(page_number - 1)
        pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
        return RenderedPage(
            page_number=page_number,
            page_count=document.page_count,
            data=pixmap.tobytes("png"),
            mime_type="image/png",
            width=pixmap.width,
            height=pixmap.height,
        )
    finally:
        document.close()
