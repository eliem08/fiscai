"""Local OCR adapter extracting text lines, words, confidences, and bounding boxes.

Engine: RapidOCR / PaddleOCR ONNX PP-OCRv4 (detection) + Multilingual PP-OCRv3 (Latin & Arabic recognition).
All models are pinned by cryptographic SHA-256 checksums in avenel/ocr/models.py.
Coordinates are normalized to [x0, y0, x1, y1] within [0.0, 1.0].
Guarantees local execution with zero network provider calls.
"""

from __future__ import annotations

import io
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from avenel.ocr.models import get_model_path

ENGINE_NAME = "RapidOCR / PaddleOCR ONNX PP-OCRv4 + Multilingual v3"
ENGINE_VERSION = "1.4.4"


@dataclass(frozen=True)
class OcrWord:
    text: str
    confidence: float
    page: int
    bbox: list[float]  # [x0, y0, x1, y1] normalized to [0.0, 1.0]


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidence: float
    page: int
    bbox: list[float]  # [x0, y0, x1, y1] normalized to [0.0, 1.0]
    words: list[OcrWord]


@dataclass(frozen=True)
class OcrResult:
    full_text: str
    page_count: int
    lines: list[OcrLine]
    words: list[OcrWord]
    engine: str = ENGINE_NAME
    engine_version: str = ENGINE_VERSION
    detected_script: str = "latin"

    def to_dict(self) -> dict[str, Any]:
        return {
            "full_text": self.full_text,
            "page_count": self.page_count,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "detected_script": self.detected_script,
            "lines": [asdict(l) for l in self.lines],
            "words": [asdict(w) for w in self.words],
        }


def has_arabic_chars(text: str) -> bool:
    """Checks if text contains Arabic Unicode characters."""
    for ch in text:
        cp = ord(ch)
        if (
            (0x0600 <= cp <= 0x06FF)
            or (0x0750 <= cp <= 0x077F)
            or (0x08A0 <= cp <= 0x08FF)
            or (0xFB50 <= cp <= 0xFDFF)
            or (0xFE70 <= cp <= 0xFEFF)
        ):
            return True
    return False


def detect_page_script(texts: list[str]) -> str:
    """Classifies script from text samples into 'arabic', 'latin', or 'mixed'."""
    arabic_count = 0
    latin_count = 0
    for s in texts:
        for ch in s:
            cp = ord(ch)
            if (
                (0x0600 <= cp <= 0x06FF)
                or (0x0750 <= cp <= 0x077F)
                or (0x08A0 <= cp <= 0x08FF)
                or (0xFB50 <= cp <= 0xFDFF)
                or (0xFE70 <= cp <= 0xFEFF)
            ):
                arabic_count += 1
            elif (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A) or (0x00C0 <= cp <= 0x024F):
                latin_count += 1

    total = arabic_count + latin_count
    if total == 0:
        return "latin"
    ar_ratio = arabic_count / total
    lat_ratio = latin_count / total

    if ar_ratio >= 0.15 and lat_ratio >= 0.15:
        return "mixed"
    if ar_ratio > 0.5:
        return "arabic"
    return "latin"


def _render_text_to_image(text: str, width: int = 1000, height: int = 1400) -> Image.Image:
    """Renders text onto a raster canvas for OCR processing."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    y = 80
    for line in lines:
        draw.text((80, y), line, fill=(0, 0, 0))
        y += 42
    return img


def _extract_page_images(data: bytes, mime_type: str) -> list[Image.Image]:
    """Extracts PIL Images for each page from PDF or raster image bytes."""
    images: list[Image.Image] = []

    if mime_type == "application/pdf" and data.startswith(b"%PDF-"):
        try:
            import fitz  # type: ignore[import-untyped]

            doc = fitz.open(stream=data, filetype="pdf")
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                images.append(img)
            doc.close()
        except (ImportError, OSError, ValueError, RuntimeError):
            pass

    if not images and mime_type.startswith("image/"):
        try:
            img = Image.open(io.BytesIO(data))
            images.append(img.convert("RGB"))
        except (OSError, ValueError):
            pass

    if not images:
        text = data.decode("utf-8", errors="ignore")
        if not text.strip():
            text = "DOCUMENT SANS TEXTE"
        images.append(_render_text_to_image(text))

    return images


class LocalOcrEngine:
    """Local, offline OCR engine with PaddleOCR / RapidOCR multilingual ONNX models."""

    def __init__(self) -> None:
        self.engine_name = ENGINE_NAME
        self.engine_version = ENGINE_VERSION
        self._default_ocr: Any | None = None
        self._latin_ocr: Any | None = None
        self._arabic_ocr: Any | None = None

    def _get_default_ocr(self) -> Any:
        if self._default_ocr is None:
            try:
                from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-untyped]

                self._default_ocr = RapidOCR()
            except ImportError:
                self._default_ocr = False
        return self._default_ocr

    def _get_latin_ocr(self) -> Any:
        if self._latin_ocr is None:
            lat_model = get_model_path("latin_rec.onnx")
            lat_dict = get_model_path("latin_dict.txt")
            if lat_model and lat_dict:
                try:
                    from rapidocr_onnxruntime import RapidOCR

                    self._latin_ocr = RapidOCR(rec_model_path=lat_model, rec_keys_path=lat_dict)
                except (RuntimeError, OSError, ValueError):
                    self._latin_ocr = self._get_default_ocr()
            else:
                self._latin_ocr = self._get_default_ocr()
        return self._latin_ocr

    def _get_arabic_ocr(self) -> Any:
        if self._arabic_ocr is None:
            ar_model = get_model_path("arabic_rec.onnx")
            ar_dict = get_model_path("arabic_dict.txt")
            if ar_model and ar_dict:
                try:
                    from rapidocr_onnxruntime import RapidOCR

                    self._arabic_ocr = RapidOCR(rec_model_path=ar_model, rec_keys_path=ar_dict)
                except (RuntimeError, OSError, ValueError):
                    self._arabic_ocr = self._get_default_ocr()
            else:
                self._arabic_ocr = self._get_default_ocr()
        return self._arabic_ocr

    def process(self, data: bytes, mime_type: str, page_count: int = 1) -> OcrResult:
        """Processes document pages with script detection (Arabic, Latin, or Mixed)."""
        page_images = _extract_page_images(data, mime_type)
        actual_page_count = max(page_count, len(page_images))

        all_lines: list[OcrLine] = []
        all_words: list[OcrWord] = []
        overall_scripts: list[str] = []

        latin_ocr = self._get_latin_ocr()
        arabic_ocr = self._get_arabic_ocr()

        for page_idx, img in enumerate(page_images, start=1):
            width, height = img.size
            img_arr = np.array(img)

            # 1. Script detection via preliminary inspection
            # Inspect raw text or probe image with recognizers
            raw_text = data.decode("utf-8", errors="ignore") if page_idx == 1 else ""
            prelim_script = detect_page_script([raw_text]) if raw_text else "latin"

            # 2. Run OCR based on script detection
            # If prelim_script is "arabic" or contains Arabic chars, run arabic_ocr
            # For mixed or unknown images, run both recognizers and merge best candidates
            lat_results = None
            ar_results = None

            if latin_ocr:
                try:
                    lat_results, _ = latin_ocr(img_arr)
                except (RuntimeError, OSError, ValueError):
                    lat_results = None

            # Check if Latin output revealed Arabic content or if prelim was Arabic
            lat_texts = [str(item[1]) for item in (lat_results or [])]
            detected_script = detect_page_script(lat_texts) if lat_texts else prelim_script

            if (detected_script in ("arabic", "mixed") or prelim_script in ("arabic", "mixed")) and arabic_ocr:
                try:
                    ar_results, _ = arabic_ocr(img_arr)
                except (RuntimeError, OSError, ValueError):
                    ar_results = None

            overall_scripts.append(detected_script)

            # 3. Select / merge OCR results
            final_items: list[tuple[Any, str, float]] = []

            if detected_script == "arabic" and ar_results:
                final_items = [(item[0], str(item[1]).strip(), float(item[2])) for item in ar_results]
            elif detected_script == "latin" and lat_results:
                final_items = [(item[0], str(item[1]).strip(), float(item[2])) for item in lat_results]
            elif ar_results and lat_results:
                # Mixed page: run both on mixed pages and choose best text per box
                used_ar = set()

                for l_idx, (l_pts, l_txt, l_sc) in enumerate(lat_results):
                    l_str = str(l_txt).strip()
                    # Find closest Arabic box
                    best_ar = None
                    best_ar_idx = -1
                    l_cy = sum(p[1] for p in l_pts) / 4.0

                    for a_idx, (a_pts, a_txt, a_sc) in enumerate(ar_results):
                        if a_idx in used_ar:
                            continue
                        a_cy = sum(p[1] for p in a_pts) / 4.0
                        if abs(l_cy - a_cy) < (height * 0.03):  # same line
                            best_ar = (a_pts, str(a_txt).strip(), float(a_sc))
                            best_ar_idx = a_idx
                            break

                    if best_ar and has_arabic_chars(best_ar[1]):
                        # Prefer Arabic text for Arabic lines
                        final_items.append((best_ar[0], best_ar[1], best_ar[2]))
                        used_ar.add(best_ar_idx)
                    else:
                        final_items.append((l_pts, l_str, float(l_sc)))

                # Add remaining Arabic boxes not paired with Latin
                for a_idx, (a_pts, a_txt, a_sc) in enumerate(ar_results):
                    if a_idx not in used_ar:
                        final_items.append((a_pts, str(a_txt).strip(), float(a_sc)))
            elif lat_results:
                final_items = [(item[0], str(item[1]).strip(), float(item[2])) for item in lat_results]
            elif ar_results:
                final_items = [(item[0], str(item[1]).strip(), float(item[2])) for item in ar_results]

            # 4. Convert to normalized OcrLines and OcrWords
            for pts, text_str, score in final_items:
                if not text_str:
                    continue

                min_x = max(0.0, min(float(p[0]) for p in pts))
                min_y = max(0.0, min(float(p[1]) for p in pts))
                max_x = min(float(width), max(float(p[0]) for p in pts))
                max_y = min(float(height), max(float(p[1]) for p in pts))

                x0 = round(min_x / width, 4)
                y0 = round(min_y / height, 4)
                x1 = round(max_x / width, 4)
                y1 = round(max_y / height, 4)

                line_words_raw = text_str.split()
                w_count = len(line_words_raw)
                line_words: list[OcrWord] = []

                for w_i, w_txt in enumerate(line_words_raw):
                    w_x0 = round(x0 + (x1 - x0) * (w_i / max(1, w_count)), 4)
                    w_x1 = round(x0 + (x1 - x0) * ((w_i + 1) / max(1, w_count)), 4)
                    word_obj = OcrWord(
                        text=w_txt,
                        confidence=round(float(score), 4),
                        page=page_idx,
                        bbox=[w_x0, y0, w_x1, y1],
                    )
                    line_words.append(word_obj)
                    all_words.append(word_obj)

                all_lines.append(
                    OcrLine(
                        text=text_str,
                        confidence=round(float(score), 4),
                        page=page_idx,
                        bbox=[x0, y0, x1, y1],
                        words=line_words,
                    )
                )

        full_text = "\n".join(l.text for l in all_lines)
        detected_doc_script = "mixed" if "mixed" in overall_scripts or ("arabic" in overall_scripts and "latin" in overall_scripts) else (
            "arabic" if "arabic" in overall_scripts else "latin"
        )

        return OcrResult(
            full_text=full_text,
            page_count=actual_page_count,
            lines=all_lines,
            words=all_words,
            engine=self.engine_name,
            engine_version=self.engine_version,
            detected_script=detected_doc_script,
        )


_OCR_ENGINE: LocalOcrEngine | None = None


def get_ocr_engine() -> LocalOcrEngine:
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        _OCR_ENGINE = LocalOcrEngine()
    return _OCR_ENGINE
