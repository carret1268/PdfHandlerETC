import argparse
from pathlib import Path
import sys

from .pdf_handler import PdfHandler


def main() -> None:
    parser = argparse.ArgumentParser(
        description="📄 PdfHandlerETC – Command-line PDF utility for encryption, extraction, and more."
    )
    parser.add_argument("--version", action="version", version="PdfHandlerETC 0.1.0")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Extract text
    extract = subparsers.add_parser("extract", help="Extract text from a PDF")
    extract.add_argument("pdf", type=Path)
    extract.add_argument("--pages", type=str, default=None)

    # Word count
    wordcount = subparsers.add_parser("wordcount", help="Count words in a PDF")
    wordcount.add_argument("pdf", type=Path)
    wordcount.add_argument("--pages", type=str, default=None)

    # Encrypt
    encrypt = subparsers.add_parser("encrypt", help="Encrypt a PDF")
    encrypt.add_argument("pdf", type=Path)
    encrypt.add_argument("--output", type=Path, default=None)
    encrypt.add_argument("--in-place", action="store_true")

    # Decrypt
    decrypt = subparsers.add_parser("decrypt", help="Decrypt a PDF")
    decrypt.add_argument("pdf", type=Path)
    decrypt.add_argument("--output", type=Path, default=None)
    decrypt.add_argument("--in-place", action="store_true")

    # Permissions
    perms = subparsers.add_parser(
        "permissions", help="Show PDF encryption and permission flags"
    )
    perms.add_argument("pdf", type=Path)

    # Resize
    resize = subparsers.add_parser("resize", help="Resize pages in a PDF")
    resize.add_argument("pdf", type=Path)
    resize.add_argument("width", type=int, help="Width in points (1in = 72pt)")
    resize.add_argument("height", type=int, help="Height in points (1in = 72pt)")
    resize.add_argument("--output", type=Path, default=None)

    # Duplicate check
    dupe = subparsers.add_parser(
        "dupe-check", help="Check if two PDFs are textually identical"
    )
    dupe.add_argument("pdf0", type=Path)
    dupe.add_argument("pdf1", type=Path)

    # Merge
    merge = subparsers.add_parser("merge", help="Merge two PDFs into one")
    merge.add_argument("pdf0", type=Path, help="First PDF (comes first in output)")
    merge.add_argument("pdf1", type=Path, help="Second PDF")
    merge.add_argument("output", type=Path, help="Destination for merged output")
    merge.add_argument(
        "--add-separator",
        action="store_true",
        help="Insert black separator page between PDFs",
    )

    args = parser.parse_args()

    try:
        match args.command:
            case "extract":
                handler = PdfHandler(args.pdf)
                text = handler.get_pdf_text(args.pages)
                print(text)

            case "wordcount":
                handler = PdfHandler(args.pdf)
                count = handler.word_count(args.pages)
                print(f"Word count: {count}")

            case "encrypt":
                handler = PdfHandler(args.pdf)
                handler.encrypt(args.output, in_place=args.in_place)

            case "decrypt":
                handler = PdfHandler(args.pdf)
                handler.decrypt(args.output, in_place=args.in_place)

            case "permissions":
                handler = PdfHandler(args.pdf)
                handler.print_permissions()

            case "resize":
                handler = PdfHandler(args.pdf)
                handler.resize(args.width, args.height, output_path=args.output)

            case "dupe-check":
                are_same = PdfHandler.pdfs_are_duplicates(args.pdf0, args.pdf1)
                print("Duplicate: ✅" if are_same else "Duplicate: ❌")

            case "merge":
                PdfHandler.merge_pdfs(
                    pdf0_path=args.pdf0,
                    pdf1_path=args.pdf1,
                    output_path=args.output,
                    add_separator=args.add_separator,
                )

    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
