import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

from invoice_lens.engine import extract
from invoice_lens.model import FieldModel


@unittest.skipUnless(shutil.which("tesseract") and importlib.util.find_spec("PIL") and
                     importlib.util.find_spec("pypdfium2"), "Tesseract and OCR extras required")
class OcrTest(unittest.TestCase):
    def test_reads_amount_from_scanned_pdf(self):
        from PIL import Image, ImageDraw, ImageFont

        with tempfile.TemporaryDirectory() as directory:
            image = Image.new("RGB", (900, 260), "white")
            pen = ImageDraw.Draw(image)
            font = ImageFont.load_default(size=38)
            pen.text((42, 48), "Invoice number: ALM-2048", fill="black", font=font)
            pen.text((42, 140), "Amount payable: USD 285.00", fill="black", font=font)
            path = Path(directory) / "scan.pdf"
            image.save(path, "PDF", resolution=180)
            facts, _ = extract([path], FieldModel(), ocr=True, languages="eng")
            self.assertIn(("total", "285.00 USD", "ocr", 1),
                          [(fact.field, fact.value, fact.method, fact.page) for fact in facts])
