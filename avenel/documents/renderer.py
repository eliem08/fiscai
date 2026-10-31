"""Document page renderer for multi-page PDF and image documents.

Renders document pages into viewable page artifacts and stores them
under deterministic storage keys for the document viewer.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageDraw

from avenel.infrastructure.storage import get_storage


@dataclass(frozen=True)
class RenderedPage:
    page_number: int
    width: int
    height: int
    image_key: str
    media_type: str


@dataclass(frozen=True)
class RenderResult:
    page_count: int
    pages: list[RenderedPage]


def _render_text_fallback_png(text: str, page_number: int, total_pages: int) -> bytes:
    """Generates a real PNG bitmap for non-PDF or fallback text content."""
    width, height = 800, 1131
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), f"Page {page_number}/{total_pages}", fill=(100, 100, 100))
    y = 80
    for line in text.splitlines():
        if line.strip():
            draw.text((40, y), line.strip(), fill=(20, 20, 20))
            y += 35
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_document(
    tenant_id: str,
    document_id: str,
    data: bytes,
    mime_type: str,
) -> RenderResult:
    """Renders document pages and stores page images in storage."""
    storage = get_storage()
    pages: list[RenderedPage] = []

    if mime_type == "application/pdf" and data.startswith(b"%PDF-"):
        try:
            import fitz  # type: ignore[import-untyped]

            doc = fitz.open(stream=data, filetype="pdf")
            page_count = len(doc)
            for p, page in enumerate(doc, start=1):
                pix = page.get_pixmap(dpi=150)
                png_bytes = pix.tobytes("png")
                key = f"pages/{tenant_id}/{document_id}/page_{p}.png"
                storage.put_object(key, png_bytes, "image/png")
                pages.append(
                    RenderedPage(
                        page_number=p,
                        width=pix.width,
                        height=pix.height,
                        image_key=key,
                        media_type="image/png",
                    )
                )
            doc.close()
            return RenderResult(page_count=page_count, pages=pages)
        except (ImportError, OSError, ValueError, RuntimeError):
            pass

    if mime_type.startswith("image/"):
        try:
            img = Image.open(io.BytesIO(data))
            width, height = img.size
            key = f"pages/{tenant_id}/{document_id}/page_1.png"
            storage.put_object(key, data, mime_type)
            pages.append(
                RenderedPage(
                    page_number=1,
                    width=width,
                    height=height,
                    image_key=key,
                    media_type=mime_type,
                )
            )
            return RenderResult(page_count=1, pages=pages)
        except (OSError, ValueError):
            pass

    # Fallback: render text to PNG
    raw_text = data.decode("utf-8", errors="ignore")
    png_bytes = _render_text_fallback_png(raw_text, page_number=1, total_pages=1)
    key = f"pages/{tenant_id}/{document_id}/page_1.png"
    storage.put_object(key, png_bytes, "image/png")
    pages.append(
        RenderedPage(
            page_number=1,
            width=800,
            height=1131,
            image_key=key,
            media_type="image/png",
        )
    )
    return RenderResult(page_count=1, pages=pages)
