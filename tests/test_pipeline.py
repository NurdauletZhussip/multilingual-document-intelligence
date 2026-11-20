import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

from invoice_lens.engine import ask, canonical, extract
from invoice_lens.model import FieldModel

SAMPLES = Path(__file__).resolve().parents[1] / "examples"


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = FieldModel()

    def answer(self, files, question):
        rows, warnings = extract(files, self.model)
        self.assertFalse(warnings)
        return ask(question, self.model, rows, [p.name for p in files])

    def test_translations_and_revision_disagreement(self):
        copies = [SAMPLES / f"invoice-{code}.txt" for code in ["kk", "ru"]]
        answer = self.answer(copies, "How much is the total?")
        self.assertEqual(answer["status"], "answered")
        self.assertEqual(answer["answers"][0]["value"], "280000.00 KZT")
        self.assertEqual(len(answer["answers"][0]["citations"]), 2)
        result = self.answer(copies + [SAMPLES / "invoice-en-revision.pdf"], "Жалпы сома қандай?")
        self.assertEqual(result["status"], "conflict")
        self.assertEqual([a["value"] for a in result["answers"]], ["280000.00 KZT", "285000.00 KZT"])
        cite = result["answers"][1]["citations"][0]
        self.assertEqual((cite["source"], cite["page"], cite["method"]), ("invoice-en-revision.pdf", 2, "pdf"))
        self.assertIn("285,000.00", cite["quote"])

    def test_do_not_merge_unrelated_invoices_or_guess_missing_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            other = Path(directory) / "other.txt"
            other.write_text("Invoice ID: M-18\n", encoding="utf-8")
            copies = [other, SAMPLES / "invoice-ru.txt"]
            self.assertEqual(self.answer(copies, "Who is the supplier?")["status"], "select_one_invoice")
            self.assertEqual(self.answer([other], "Who is the supplier?")["status"], "missing")

    def test_unsupported_and_invalid_values(self):
        self.assertEqual(self.answer([SAMPLES / "invoice-kk.txt"], "What is the bank account?")["status"],
                         "unsupported_question")
        for text in ["USD 12,34,99", "10 apples", "20.005 KZT", "10 USD and 12 EUR"]:
            self.assertIsNone(canonical("total", text))
        self.assertIsNone(canonical("due_date", "31.02.2026"))
        self.assertIsNone(canonical("invoice_id", "1 / 3"))

    def test_image_only_page_is_disclosed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "blank.pdf"
            writer = PdfWriter()
            writer.add_blank_page(100, 100)
            writer.write(source)
            facts, warnings = extract([source], self.model)
            self.assertFalse(facts)
            self.assertIn("page 1: no readable text", warnings[0])
