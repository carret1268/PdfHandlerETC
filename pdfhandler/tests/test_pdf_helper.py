import unittest
from pathlib import Path

from pdfhandler.pdf_handler import PdfHandler, PageNumberType


FIXTURES_DIR = Path(__file__).parent / "fixtures"
GJ_PDF = FIXTURES_DIR / "GJ-10238.pdf"


class TestPageParsingHelpers(unittest.TestCase):
    def test_get_page_numbers_from_str_simple(self) -> None:
        result = PdfHandler._get_page_numbers_from_str("1, 3, 5")
        self.assertEqual(result, [1, 3, 5])

    def test_get_page_numbers_from_str_with_ranges_and_and(self) -> None:
        result = PdfHandler._get_page_numbers_from_str("1, 3-5 and 7")
        self.assertEqual(result, [1, 3, 4, 5, 7])

    def test_parse_page_numbers_str(self) -> None:
        pages: PageNumberType = "2-4"
        indices = PdfHandler._parse_page_numbers(pages)
        self.assertEqual(indices, [1, 2, 3])  # 1-indexed -> 0-indexed

    def test_parse_page_numbers_int(self) -> None:
        pages: PageNumberType = 3
        indices = PdfHandler._parse_page_numbers(pages)
        self.assertEqual(indices, [2])

    def test_parse_page_numbers_list_mixed(self) -> None:
        pages: PageNumberType = [1, "3-4", "6 and 8"]
        indices = PdfHandler._parse_page_numbers(pages)
        # 1, 3, 4, 6, 8 -> 0, 2, 3, 5, 7
        self.assertEqual(indices, [0, 2, 3, 5, 7])


class TestPdfHandlerIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not GJ_PDF.exists():
            raise unittest.SkipTest(
                f"Fixture PDF not found at {GJ_PDF}. Place GJ-10238.pdf in tests/fixtures/."
            )

    def test_init_requires_pdf_suffix(self) -> None:
        with self.assertRaises(ValueError):
            PdfHandler(GJ_PDF.with_suffix(".txt"))

    def test_get_pdf_text_entire_doc_not_empty(self) -> None:
        handler = PdfHandler(GJ_PDF)
        text = handler.get_pdf_text()
        # Just a sanity check: we expect some text, not necessarily a value
        self.assertIsInstance(text, str)
        self.assertNotEqual(text.strip(), "")

    def test_word_count_positive(self) -> None:
        handler = PdfHandler(GJ_PDF)
        count = handler.word_count()
        self.assertIsInstance(count, int)
        self.assertGreater(count, 0)

    def test_pdfs_are_duplicates_same_file(self) -> None:
        self.assertTrue(
            PdfHandler.pdfs_are_duplicates(GJ_PDF, GJ_PDF),
            "Same file should be detected as duplicate.",
        )


if __name__ == "__main__":
    unittest.main()
