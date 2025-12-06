[![PyPI](https://img.shields.io/pypi/v/pdfhandleretc.svg)](https://pypi.org/project/pdfhandleretc/) [![Documentation Status](https://readthedocs.org/projects/pdfhandleretc/badge/?version=latest)](https://pdfhandleretc.readthedocs.io/en/latest/) [![CI](https://github.com/carret1268/PdfHandlerETC/actions/workflows/ci.yml/badge.svg)](https://github.com/carret1268/PdfHandlerETC/actions/workflows/ci.yml) [![codecov](https://codecov.io/github/carret1268/PdfHandlerETC/branch/main/graph/badge.svg)](https://codecov.io/github/carret1268/PdfHandlerETC)

# PdfHandlerETC

PdfHandlerETC is a lightweight command-line and Python toolkit for handling common PDF tasks including text extraction, encryption, decryption, permissions inspection, word counting, page resizing, and file merging.

This project is released under the [CC0 1.0 Public Domain Dedication](https://creativecommons.org/publicdomain/zero/1.0/).

## Features

- Extract text from PDFs by page or range
- Encrypt and decrypt PDFs with customizable permissions
- Count words across entire documents or selected pages
- Inspect encryption status and permissions
- Resize page dimensions
- Merge two PDFs with optional visual separators (blank page or black bar)
- Detect duplicate PDFs based on text content
- Includes both a Python API and command-line interface (CLI)

## Installation

Install from PyPI:

```bash
pip install pdfhandleretc
```

## Command-Line Usage

After installation, you can use the `pdfhandler` CLI tool:

```bash
python -m pdfhandler wordcount document.pdf --pages "1, 3" > document_text.txt
python -m pdfhandler encrypt document.pdf --output secure.pdf
python -m pdfhandler decrypt secure.pdf --in-place
python -m pdfhandler permissions secure.pdf
python -m pdfhandler resize document.pdf 612 792 --output resized.pdf
python -m pdfhandler dupe-check file1.pdf file2.pdf
python -m pdfhandler merge intro.pdf appendix.pdf merged.pdf --add-separator black
python -m pdfhandler extract document.pdf --pages "1-3, 5"
```

Use `--help` for details:

```bash
python -m pdfhandler --help
python -m pdfhandler extract --help
```

## Python Usage

```python
from pdfhandler import PdfHandler

handler = PdfHandler("example.pdf")

# Extract text
text = handler.get_pdf_text("1-2, 4")
print(text)

# Word count
print("Words:", handler.word_count("1-3"))

# Encrypt the file
handler.encrypt(output="example-encrypted.pdf")

# Show permissions
handler.print_permissions()

# Resize pages
handler.resize(width=612, height=792, output_path="resized.pdf")

# Merge with a visual separator (black bar or blank page)
PdfHandler.merge_pdfs(
    "intro.pdf",
    "appendix.pdf",
    "merged.pdf",
    add_separator=True,
    separator_type="black"  # or "blank"
)
```

## License

This project is licensed under the [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/) public domain dedication. You may use, modify, and distribute it freely without attribution or restriction.

## Dependencies

- pdfminer.six - for text extraction
- pikepdf - for encryption and PDF manipulation
- colorama - for cross-platform terminal colors
