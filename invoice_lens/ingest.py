"""Keep physical page boundaries through native extraction and optional OCR."""

import io
import re
import shutil
import subprocess
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError


def recognize(image, languages):
    if not re.fullmatch(r"[a-z]{3}(?:\+[a-z]{3})*", languages):
        raise ValueError("Use Tesseract language codes such as kaz+rus+eng.")
    executable = shutil.which("tesseract")
    if not executable:
        raise ValueError("Install Tesseract and the requested language packs to use --ocr.")
    command = [executable, "stdin", "stdout", "-l", languages, "--psm", "6",
               "-c", "preserve_interword_spaces=1"]
    try:
        result = subprocess.run(command, input=image, capture_output=True, timeout=90)
    except subprocess.TimeoutExpired as error:
        raise ValueError("OCR exceeded its 90-second limit for this page.") from error
    if result.returncode:
        raise ValueError("Tesseract failed: " + result.stderr.decode("utf-8", "replace").strip())
    return result.stdout.decode("utf-8")


def ocr_page(path, index, languages):
    try:
        import pypdfium2 as pdfium
        from PIL import Image  # noqa: F401 -- needed by the bitmap adapter
    except ImportError as error:
        raise ValueError("Install the optional OCR dependencies with pip install '.[ocr]'.") from error
    with pdfium.PdfDocument(str(path)) as pdf:
        page = pdf[index]
        width, height = page.get_size()
        scale = min(3.0, 4800 / max(width, height))
        image = page.render(scale=scale).to_pil()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
    return recognize(buffer.getvalue(), languages)


def read_pages(path: Path, ocr=False, languages="kaz+rus+eng"):
    suffix = path.suffix.lower()
    if suffix == ".txt":
        pages = path.read_text(encoding="utf-8-sig").split("\f")
        return [(text, "text") for text in pages]
    if suffix in {".png", ".jpg", ".jpeg"}:
        if not ocr:
            raise ValueError(f"{path.name} needs --ocr for image input.")
        return [(recognize(path.read_bytes(), languages), "ocr")]
    if suffix != ".pdf":
        raise ValueError(f"Unsupported extension {suffix!r}. Use PDF, TXT, PNG or JPEG.")
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError(f"{path.name} is encrypted. Supply an unlocked copy.")
        pages = []
        for index, page in enumerate(reader.pages):
            text = page.extract_text(extraction_mode="layout") or ""
            if text.strip():
                pages.append((text, "pdf"))
            elif ocr:
                pages.append((ocr_page(path, index, languages), "ocr"))
            else:
                pages.append(("", "no_text"))
        return pages
    except PyPdfError as error:
        raise ValueError(f"Unable to read {path.name}: {error}") from error
