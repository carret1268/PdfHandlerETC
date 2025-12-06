from cmath import exp
import io
import sys
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pikepdf

from pdfhandler import PdfHandler, __main__ as cli  # imports main() and PdfHandler

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
GJ_PDF = FIXTURES_DIR / "GJ-10238.pdf"
FS_PDF = FIXTURES_DIR / "FS-38373_page4.pdf"


def get_pdf_first_page_size(pdf_path: Path) -> tuple[pikepdf.Array, pikepdf.Array]:
    with pikepdf.open(pdf_path) as pdf:
        mediabox = pdf.pages[0].mediabox
        cropbox = pdf.pages[0].cropbox
    return mediabox, cropbox


class TestCli(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not GJ_PDF.exists():
            raise unittest.SkipTest(
                f"Fixture PDF not found at {GJ_PDF}. Place GJ-10238.pdf in tests/fixtures/."
            )

    def test_extract_full_pdf(self) -> None:
        argv = ["pdfhandler", "extract", str(GJ_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue()

        self.assertIsInstance(output, str)
        self.assertNotEqual(output.strip(), "")
        self.assertIn("The fish tissue used in this study was cod fillet", output)

    def test_extract_first_page(self) -> None:
        argv = ["pdfhandler", "extract", "--pages", "1", str(GJ_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue()

        self.assertIsInstance(output, str)
        self.assertNotEqual(output.strip(), "")
        self.assertNotIn("The fish tissue used in this study was cod fillet", output)
        self.assertIn("Extraction and analysis of PCBs from fish", output)

    def test_wordcount(self) -> None:
        argv = ["pdfhandler", "wordcount", str(GJ_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue().strip()

        # Expect something like "Word count: 1234"
        self.assertTrue(output.startswith("Word count: "))
        _, _, value = output.partition(": ")
        self.assertGreater(int(value), 0)
        self.assertEqual(int(value), 1374)

        argv = ["pdfhandler", "wordcount", "--pages", "1 and 3", str(GJ_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue().strip()

        self.assertTrue(output.startswith("Word count: "))
        _, _, value = output.partition(": ")
        self.assertGreater(int(value), 0)
        self.assertEqual(int(value), 761)

        # no error throws when indicated pages are outside range
        argv = ["pdfhandler", "wordcount", "--pages", "2,3-20", str(GJ_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue().strip()

        self.assertTrue(output.startswith("Word count: "))
        _, _, value = output.partition(": ")
        self.assertGreater(int(value), 0)
        self.assertEqual(int(value), 938)

    def test_permissions_encryption_and_decryption(self) -> None:
        argv = ["pdfhandler", "permissions", str(GJ_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue().strip()

        self.assertIsInstance(output, str)
        self.assertIn("Is encrypted: False", output)
        self.assertIn("extract: True", output)
        self.assertIn("modify_annotation: True", output)
        self.assertIn("modify_assembly: True", output)
        self.assertIn("modify_form: True", output)
        self.assertIn("modify_other: True", output)
        self.assertIn("print_lowres: True", output)
        self.assertIn("print_highres: True", output)

        ENC_PDF = GJ_PDF.parent / "encrypted.pdf"
        argv = ["pdfhandler", "encrypt", "--output", str(ENC_PDF), str(GJ_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue().strip()

        self.assertTrue(ENC_PDF.exists())

        argv = ["pdfhandler", "permissions", str(ENC_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue().strip()

        self.assertIsInstance(output, str)
        self.assertIn("Is encrypted: True", output)
        self.assertIn("extract: False", output)
        self.assertIn("modify_annotation: False", output)
        self.assertIn("modify_assembly: False", output)
        self.assertIn("modify_form: False", output)
        self.assertIn("modify_other: False", output)
        self.assertIn("print_lowres: False", output)
        self.assertIn("print_highres: False", output)

        DEC_PDF = GJ_PDF.parent / "decrypted.pdf"
        argv = ["pdfhandler", "decrypt", "--output", str(DEC_PDF), str(ENC_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue().strip()

        self.assertTrue(DEC_PDF.exists())

        argv = ["pdfhandler", "permissions", str(DEC_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue().strip()

        self.assertIsInstance(output, str)
        self.assertIn("Is encrypted: False", output)
        self.assertIn("extract: True", output)
        self.assertIn("modify_annotation: True", output)
        self.assertIn("modify_assembly: True", output)
        self.assertIn("modify_form: True", output)
        self.assertIn("modify_other: True", output)
        self.assertIn("print_lowres: True", output)
        self.assertIn("print_highres: True", output)

        enc_pdf = PdfHandler(ENC_PDF)
        enc_pdf.rm()

        self.assertFalse(ENC_PDF.exists())

        dec_pdf = PdfHandler(DEC_PDF)
        dec_pdf.rm()

        self.assertFalse(DEC_PDF.exists())

    def test_resize(self) -> None:
        expected_size = pikepdf.Array(
            [Decimal("0"), Decimal("0"), Decimal("612.0"), Decimal("792.0")]
        )

        og_mediabox, og_cropbox = get_pdf_first_page_size(GJ_PDF)

        self.assertTrue(expected_size == og_mediabox)
        self.assertTrue(expected_size == og_cropbox)

        new_width = "200"
        new_height = "400"

        expected_size = pikepdf.Array(
            [Decimal("0"), Decimal("0"), Decimal(f"{new_width}"), Decimal(f"{new_height}")]
        )

        expected_resized_path = GJ_PDF.parent / f"{GJ_PDF.stem}-{new_width}x{new_height}.pdf"

        argv = ["pdfhandler", "resize", str(GJ_PDF), new_width, new_height]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()

        self.assertTrue(expected_resized_path.exists())

        new_mediabox, new_cropbox = get_pdf_first_page_size(expected_resized_path)

        self.assertEqual(expected_size, new_mediabox)
        self.assertEqual(expected_size, new_cropbox)

        resized_pdf = PdfHandler(expected_resized_path)
        resized_pdf.rm()

        self.assertFalse(expected_resized_path.exists())

    def test_dupe_check(self) -> None:
        CP_PDF = GJ_PDF.parent / f"{GJ_PDF.stem}-copy.pdf"
        ph_GJ_PDF = PdfHandler(GJ_PDF)
        ph_GJ_PDF.cp(CP_PDF)

        self.assertTrue(CP_PDF.exists())

        argv = ["pdfhandler", "dupe-check", str(GJ_PDF), str(CP_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue().strip()

        self.assertEqual("Duplicate: YES", output)

        ph_CP_PDF = PdfHandler(CP_PDF)
        ph_CP_PDF.rm()

        self.assertFalse(CP_PDF.exists())

        argv = ["pdfhandler", "dupe-check", str(GJ_PDF), str(FS_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue().strip()

        self.assertEqual("Duplicate: NO", output)

    def test_merge(self) -> None:
        out_PDF = GJ_PDF.parent / "merged.pdf"

        with pikepdf.open(GJ_PDF) as pdf:
            self.assertTrue(len(pdf.pages) == 3)
        with pikepdf.open(FS_PDF) as pdf:
            self.assertTrue(len(pdf.pages) == 1)

        argv = ["pdfhandler", "merge", str(GJ_PDF), str(FS_PDF), str(out_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()

        self.assertTrue(out_PDF.exists())

        with pikepdf.open(out_PDF) as pdf:
            self.assertTrue(len(pdf.pages) == 4)

        argv = ["pdfhandler", "extract", "--pages", "1,4", str(out_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue().strip()

        self.assertIn("Bromodichloromethane (99% pure)", output)
        self.assertIn("other marine tissues continues to be a necessary step", output)

        ph_OUT_PDF = PdfHandler(out_PDF)
        ph_OUT_PDF.rm()

    def test_merge_with_separator(self) -> None:
        out_PDF = GJ_PDF.parent / "merged.pdf"

        with pikepdf.open(GJ_PDF) as pdf:
            self.assertTrue(len(pdf.pages) == 3)
        with pikepdf.open(FS_PDF) as pdf:
            self.assertTrue(len(pdf.pages) == 1)

        argv = ["pdfhandler", "merge", "--add-separator", str(GJ_PDF), str(FS_PDF), str(out_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()

        self.assertTrue(out_PDF.exists())

        with pikepdf.open(out_PDF) as pdf:
            self.assertTrue(len(pdf.pages) == 5)

        argv = ["pdfhandler", "extract", "--pages", "1,5", str(out_PDF)]

        with patch.object(sys, "argv", argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                cli.main()
            output = buf.getvalue().strip()

        self.assertIn("Bromodichloromethane (99% pure)", output)
        self.assertIn("other marine tissues continues to be a necessary step", output)

        ph_OUT_PDF = PdfHandler(out_PDF)
        ph_OUT_PDF.rm()


if __name__ == "__main__":
    unittest.main()
