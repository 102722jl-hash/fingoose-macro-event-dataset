from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class OfficialPdfPlumberTests(unittest.TestCase):
    def test_pdfplumber_fallback_extracts_page_text(self) -> None:
        from fingoose_official_pdf import extract_pdf_pages_pdfplumber

        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_dir:
            path = Path(temp_dir) / "sample.pdf"
            pdf = canvas.Canvas(str(path))
            pdf.drawString(72, 720, "Official annual report business exposure")
            pdf.save()

            rows = extract_pdf_pages_pdfplumber(path, source_id="source-test")

        self.assertEqual(len(rows), 1)
        self.assertIn("business exposure", rows[0]["text"])
        self.assertEqual(rows[0]["extraction_engine"], "pdfplumber")


if __name__ == "__main__":
    unittest.main()
