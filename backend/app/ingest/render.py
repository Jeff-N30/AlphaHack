"""Turn PDF / image files into page images + optional digital text layer."""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
import pymupdf
from PIL import Image, ImageOps

_ALLOWED = frozenset({".pdf", ".png", ".jpg", ".jpeg"})
_MAX_PX = 2000
_DPI = 200


@dataclass
class PagePreview:
    page: int
    text: str
    image_png: bytes | None = None
    method: str = "empty"  # pdf_text | ocr | image_text | empty
    char_count: int = 0


@dataclass
class DocumentPreview:
    path: Path
    pages: list[PagePreview] = field(default_factory=list)
    error: str | None = None

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text).strip()

    @property
    def method(self) -> str:
        if not self.pages:
            return "empty"
        methods = {p.method for p in self.pages}
        if "ocr" in methods:
            return "ocr"
        if "pdf_text" in methods:
            return "pdf_text"
        if "image_text" in methods:
            return "image_text"
        return "empty"


def allowed_suffix(path: Path) -> bool:
    return path.suffix.lower() in _ALLOWED


def _normalize_image(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, _MAX_PX / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    return img


def _image_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    _normalize_image(img).save(buf, format="PNG")
    return buf.getvalue()


def _ocr_image(img: Image.Image, *, lang: str = "eng") -> tuple[str, float]:
    """Tesseract OCR. Returns (text, rough confidence 0..1)."""
    try:
        import pytesseract
    except ImportError:
        # passporteye pulls tesseract via CLI; try pillow-only path
        pytesseract = None  # type: ignore

    if pytesseract is None:
        return "", 0.0

    norm = _normalize_image(img)
    try:
        data = pytesseract.image_to_data(norm, lang=lang, output_type=pytesseract.Output.DICT)
        texts: list[str] = []
        confs: list[float] = []
        for t, c in zip(data.get("text", []), data.get("conf", []), strict=False):
            if not t or not str(t).strip():
                continue
            texts.append(str(t).strip())
            try:
                cf = float(c)
                if cf >= 0:
                    confs.append(cf / 100.0)
            except (TypeError, ValueError):
                pass
        text = " ".join(texts)
        conf = sum(confs) / len(confs) if confs else (0.5 if text else 0.0)
        return text, conf
    except Exception:
        try:
            text = pytesseract.image_to_string(norm, lang=lang) or ""
            return text.strip(), 0.4 if text.strip() else 0.0
        except Exception:
            return "", 0.0


def _pdf_text_layer(path: Path) -> list[str]:
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages.append((page.extract_text() or "").strip())
    return pages


def _pdf_render_pages(path: Path) -> list[Image.Image]:
    doc = pymupdf.open(path)
    images: list[Image.Image] = []
    zoom = _DPI / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    try:
        for i in range(len(doc)):
            pix = doc.load_page(i).get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            images.append(_normalize_image(img))
    finally:
        doc.close()
    return images


def read_preview(path: Path | str, *, max_pages: int = 4, ocr_lang: str = "eng") -> DocumentPreview:
    """Build text preview for a single uploaded file (PDF or image)."""
    path = Path(path)
    out = DocumentPreview(path=path)
    if not path.exists():
        out.error = "missing"
        return out
    if not allowed_suffix(path):
        out.error = "unsupported_type"
        return out

    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg"}:
        img = Image.open(path)
        img = _normalize_image(img)
        text, _conf = _ocr_image(img, lang=ocr_lang)
        method = "image_text" if text else "empty"
        out.pages.append(
            PagePreview(
                page=1,
                text=text,
                image_png=_image_to_png_bytes(img),
                method=method,
                char_count=len(text),
            )
        )
        return out

    # PDF
    try:
        text_pages = _pdf_text_layer(path)
    except Exception as exc:
        out.error = f"pdf_open:{exc}"
        return out

    n = min(len(text_pages), max_pages)
    rich = sum(1 for t in text_pages[:n] if len(t) >= 40)
    if rich >= max(1, n // 2) or (n == 1 and len(text_pages[0]) >= 40):
        for i, t in enumerate(text_pages[:n], start=1):
            out.pages.append(
                PagePreview(page=i, text=t, method="pdf_text" if t else "empty", char_count=len(t))
            )
        return out

    # Scanned / image-only PDF → render + OCR
    try:
        images = _pdf_render_pages(path)[:max_pages]
    except Exception as exc:
        out.error = f"pdf_render:{exc}"
        return out

    for i, img in enumerate(images, start=1):
        layer = text_pages[i - 1] if i - 1 < len(text_pages) else ""
        if len(layer) >= 40:
            text, method = layer, "pdf_text"
        else:
            text, _c = _ocr_image(img, lang=ocr_lang)
            method = "ocr" if text else "empty"
        out.pages.append(
            PagePreview(
                page=i,
                text=text,
                image_png=_image_to_png_bytes(img),
                method=method,
                char_count=len(text),
            )
        )
    return out
