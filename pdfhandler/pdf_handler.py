"""High-level utilities for inspecting and modifying PDF files.

This module exposes :class:`PdfHandler`, a convenience wrapper around ``pikepdf``
and ``pdfminer`` for:

* text extraction and word counting
* encryption, decryption, and permission inspection
* moving, deleting, and resizing PDFs
* merging PDFs with optional separator pages
"""

import logging
import re
import shutil
from importlib.resources import as_file
from pathlib import Path
from typing import Literal, cast

import pikepdf
from colorama import Fore, init
from pdfminer.high_level import extract_text

PageNumberType = int | str | list[int | str] | None
PathType = Path | str
PathNoneType = PathType | None


class PdfHandler:
    """Helper for common operations on a single PDF file.

    The handler validates the input path on construction and then provides
    methods for:

    * extracting text and counting words
    * checking and changing encryption / permissions
    * moving, deleting, and resizing the file
    * merging PDFs and inserting separator pages
    """

    # Handles mixed strings like "1, 3, 5-9 and 12"
    _page_number_regex = re.compile(r"(?:[\s,]*|(?:\sand\s))(\d+)(?:-(\d+))?")

    def __init__(self, pdf_path: PathType):
        """Create a PdfHandler for the given path.

        Parameters
        ----------
        pdf_path : str | Path
            Path to an existing ``.pdf`` file.

        Raises
        ------
        ValueError
            If the path does not end with ``.pdf`` (case-insensitive).
        FileExistsError
            If no file exists at the resolved path.
        """
        self.pdf_path = Path(str(pdf_path)).resolve()
        if self.pdf_path.suffix.lower() != ".pdf":
            raise ValueError(f"PDF path suffix must be '.pdf', not {self.pdf_path.suffix}")
        if not self.pdf_path.exists():
            raise FileExistsError(f"No file exists at {self.pdf_path}")

    @classmethod
    def _get_page_numbers_from_str(cls, page_numbers: str) -> list[int]:
        """Parse a 1-indexed page-string into a sorted list of page numbers.

        Accepts mixed formatting with commas, whitespace, ``"and"``, and ranges
        using hyphens. For example, the input string ``"1, 3, 5-7 and 10"``
        will return ``[1, 3, 5, 6, 7, 10]``.

        This method does not adjust for zero-based indexing; callers must
        subtract one if 0-indexed page indices are required.

        Parameters
        ----------
        page_numbers : str
            A string representing page numbers to include. Acceptable formats
            include:

            * single numbers (e.g., ``"3"``)
            * comma-separated numbers (e.g., ``"1, 2, 3"``)
            * ranges using hyphens (e.g., ``"4-6"``)
            * ``"and"`` as a delimiter (e.g., ``"2 and 5"``)
            * mixed input (e.g., ``"1, 3-4 and 6"``)

        Returns
        -------
        list[int]
            A sorted list of unique 1-indexed page numbers. Returns an empty
            list if no valid numbers are found.
        """
        page_number_matches = re.findall(cls._page_number_regex, page_numbers)

        page_numbers_set: set[int] = set()
        for match in page_number_matches:
            if match[-1] == "":
                page_numbers_set.add(int(match[0]))
            else:
                for page_number in range(int(match[0]), int(match[-1]) + 1):
                    page_numbers_set.add(page_number)

        page_numbers_list = sorted(page_numbers_set)
        return page_numbers_list

    @classmethod
    def _parse_page_numbers(cls, pages: PageNumberType) -> list[int]:
        """Normalize user-provided page numbers to 0-indexed page indices.

        Page numbers in user input are assumed to be 1-indexed and are converted
        to 0-indexed integers.

        Acceptable input formats
        ------------------------
        * ``None`` is not supported here (the caller should handle this)
        * a single ``int`` or ``str`` (e.g., ``3`` or ``"3"``)
        * a range string using a hyphen (e.g., ``"5-7"``)
        * a comma/space/``"and"``-delimited string
          (e.g., ``"1, 3 and 5-6"``)
        * a list of any combination of ``int`` and ``str``
          (e.g., ``[1, "3-4", "6 and 8"]``)

        Parameters
        ----------
        pages : PageNumberType
            The page numbers to extract, excluding ``None``. See acceptable
            formats above.

        Returns
        -------
        list[int]
            A sorted list of 0-indexed page indices.
        """
        if isinstance(pages, str):
            pages_list = cls._get_page_numbers_from_str(pages)
        elif isinstance(pages, int):
            pages_list = [pages]
        elif isinstance(pages, list):
            new_pages: set[int] = set()
            for page in pages:
                if isinstance(page, str):
                    for p in cls._get_page_numbers_from_str(page):
                        new_pages.add(p)
                else:
                    new_pages.add(int(page))
            pages_list = sorted(new_pages)
        else:
            msg = (
                f"pages must be an int, str, list[int | str], or similar value, not {type(pages)!r}"
            )
            raise TypeError(msg)

        return [int(page) - 1 for page in pages_list]

    def get_pdf_text(self, pages: PageNumberType = None) -> str:
        """Extract text from the PDF, optionally from specific pages.

        Parameters
        ----------
        pages : PageNumberType, optional
            Pages to extract text from. If ``None`` (default), all pages are
            included. Acceptable formats include:

            * a single int or str (e.g., ``5`` or ``"5"``)
            * a range as a str (e.g., ``"2-4"``)
            * a comma/space/``"and"``-delimited str
              (e.g., ``"1, 3 and 5-6"``)
            * a list of ints and/or strs (e.g., ``[1, "3", "5-7"]``)

        Returns
        -------
        str
            The extracted text as a single string. Returns an empty string if
            no text is found.
        """
        if pages is None:
            with pikepdf.open(self.pdf_path) as pdf:
                page_indices = list(range(len(pdf.pages)))
        else:
            page_indices = cast(list[int], self._parse_page_numbers(pages))

        pdf_text = extract_text(self.pdf_path, page_numbers=page_indices).strip()
        return pdf_text

    def word_count(self, pages: PageNumberType = None) -> int:
        """Count the number of words in the PDF.

        Parameters
        ----------
        pages : PageNumberType, optional
            Pages to include in the word count. If ``None`` (default), all
            pages are included. See :meth:`get_pdf_text` for accepted formats.

        Returns
        -------
        int
            The total number of words found on the specified pages.
        """
        text = self.get_pdf_text(pages)
        words = re.findall(r"\b\w+\b", text)
        return len(words)

    def pdf_is_encrypted(self) -> bool:
        """Return whether the PDF is encrypted.

        Returns
        -------
        bool
            ``True`` if the PDF is encrypted, ``False`` otherwise.
        """
        with pikepdf.open(self.pdf_path) as pike_doc:
            return pike_doc.is_encrypted

    def _get_output_path(
        self,
        in_place: bool,
        output: PathNoneType,
        suffix: str,
    ) -> Path:
        """Resolve the output path for saving a modified PDF.

        Parameters
        ----------
        in_place : bool
            If ``True``, returns the original PDF path (the file is overwritten
            in place).
        output : str | Path | None
            The desired output path. Ignored if ``in_place`` is ``True``. If
            ``None``, a default path is generated using ``suffix``.
        suffix : str
            Suffix to append to the original filename when ``output`` is
            ``None``.

        Returns
        -------
        Path
            The resolved path for saving the output PDF.

        Raises
        ------
        ValueError
            If ``output`` is provided and does not have a ``.pdf`` extension.
        """
        if in_place:
            output_path = self.pdf_path
        elif output is None:
            output_path = self.pdf_path.parent / self.pdf_path.stem / f"{suffix}.pdf"
        else:
            output_path = Path(str(output))
            if output_path.suffix.lower() != ".pdf":
                msg = (
                    "output should either be None or be a path-like object "
                    "with a '.pdf' suffix. "
                    f"Got {output!r}."
                )
                raise ValueError(msg)

        return output_path

    def save_pike_pdf(
        self,
        output: PathNoneType,
        in_place: bool = False,
        crypt_type: str | None = None,
        password: str | None = None,
        owner_password: str | None = None,
        extract: bool = True,
        modify_annotation: bool = True,
        modify_assembly: bool = True,
        modify_form: bool = True,
        modify_other: bool = True,
        print_lowres: bool = True,
        print_highres: bool = True,
    ) -> None:
        """Save the PDF with optional encryption or decryption applied.

        Parameters
        ----------
        output : str | Path | None
            Destination for the saved file. Ignored if ``in_place`` is ``True``.
            If ``None``, a new file is saved with a suffix such as
            ``"-Encrypted"`` or ``"-Decrypted"`` depending on usage.
        in_place : bool, default False
            If ``True``, overwrites the original file. If ``False``, creates a
            new file.
        crypt_type : str | None, default None
            A preset encryption mode. Must be one of:

            * ``"decrypt"`` : disables encryption entirely
            * ``"encrypt"`` : enables encryption with all permissions set
              to ``False``
            * ``"no_copy"`` : like ``"decrypt"`` but with extract permission
              set to ``False``
            * ``None`` : uses the individual permission arguments below
        password : str | None, default None
            User password for opening the encrypted PDF. If ``None`` or an
            empty string, no password is required to open.
        owner_password : str | None, default None
            Owner password used to set permissions. A default value is used if
            this is ``None``.
        extract : bool, default True
            Whether users can extract text or images.
        modify_annotation : bool, default True
            Whether users can modify annotations.
        modify_assembly : bool, default True
            Whether users can rearrange pages or merge documents.
        modify_form : bool, default True
            Whether users can fill in or edit form fields.
        modify_other : bool, default True
            Whether users can make general modifications.
        print_lowres : bool, default True
            Whether users can print in low resolution.
        print_highres : bool, default True
            Whether users can print in high resolution.

        Raises
        ------
        ValueError
            If ``crypt_type`` is invalid or if the resolved output path is
            invalid.
        """
        if password is None:
            password = ""  # nosec B105
        if owner_password is None:
            owner_password = "1234abcd"  # nosec B105

        output = self._get_output_path(in_place=in_place, output=output, suffix="")

        if crypt_type is not None:
            crypt_type = crypt_type.lower().strip()
        match crypt_type:
            case "decrypt":
                pike_encryption: pikepdf.Encryption | None = None
            case "encrypt":
                extract = False
                modify_annotation = False
                modify_assembly = False
                modify_form = False
                modify_other = False
                print_lowres = False
                print_highres = False
                pike_encryption = None
            case "no_copy":
                extract = False
                pike_encryption = None
            case None:
                pike_encryption = None
            case _:
                msg = (
                    "crypt_type must be one of ['encrypt', 'decrypt', "
                    f"'no_copy', None], not {crypt_type!r}"
                )
                raise ValueError(msg)

        if crypt_type != "decrypt":
            pike_encryption = pikepdf.Encryption(
                user=password,
                owner=owner_password,
                allow=pikepdf.Permissions(
                    extract=extract,
                    modify_annotation=modify_annotation,
                    modify_assembly=modify_assembly,
                    modify_form=modify_form,
                    modify_other=modify_other,
                    print_lowres=print_lowres,
                    print_highres=print_highres,
                ),
            )

        with pikepdf.open(self.pdf_path) as pike_doc:
            pike_doc.save(output, encryption=pike_encryption)

    def get_pdf_permissions(self) -> dict[str, bool]:
        """Return the current permission settings of the PDF.

        Returns
        -------
        dict[str, bool]
            A dictionary mapping permission names to boolean values. Keys
            include:

            * ``"extract"``
            * ``"modify_annotation"``
            * ``"modify_assembly"``
            * ``"modify_form"``
            * ``"modify_other"``
            * ``"print_lowres"``
            * ``"print_highres"``
        """
        with pikepdf.open(self.pdf_path) as pike_doc:
            permissions_dict = {
                "extract": pike_doc.allow.extract,
                "modify_annotation": pike_doc.allow.modify_annotation,
                "modify_assembly": pike_doc.allow.modify_assembly,
                "modify_form": pike_doc.allow.modify_form,
                "modify_other": pike_doc.allow.modify_other,
                "print_lowres": pike_doc.allow.print_lowres,
                "print_highres": pike_doc.allow.print_highres,
            }

        return permissions_dict

    def print_permissions(self) -> None:
        """Print encryption and permission status to the console.

        Output is color-coded using ``colorama``:

        * green for enabled permissions
        * red for disabled permissions
        """
        init()

        print(f"Permissions for {self.pdf_path}")

        is_encrypted = self.pdf_is_encrypted()
        print(
            "\tIs encrypted: "
            f"{Fore.LIGHTRED_EX if is_encrypted else Fore.LIGHTGREEN_EX}"
            f"{is_encrypted}{Fore.RESET}"
        )

        permissions_dict = self.get_pdf_permissions()
        for key, val in permissions_dict.items():
            print(f"\t\t{key}: {Fore.LIGHTGREEN_EX if val else Fore.LIGHTRED_EX}{val}{Fore.RESET}")

    def encrypt(
        self,
        output: PathNoneType = None,
        in_place: bool = False,
        password: str | None = None,
        owner_password: str | None = None,
    ) -> None:
        """Encrypt the PDF if it is not already encrypted.

        This creates an encrypted version of the PDF using restrictive
        permissions by default. If ``in_place`` is ``False``, the encrypted
        file is saved to a new path; otherwise, the original file is
        overwritten.

        For fine-grained control over permissions, use :meth:`save_pike_pdf`
        directly.

        Parameters
        ----------
        output : str | Path | None, default None
            Destination path for the encrypted PDF. Ignored if
            ``in_place=True``. If ``None``, a new file is created with
            ``"-Encrypted"`` appended to the original name.
        in_place : bool, default False
            Whether to overwrite the original file in place.
        password : str | None, default None
            The user password required to open the PDF. If ``None`` or empty,
            no password is required to view.
        owner_password : str | None, default None
            The owner password used to set encryption and permissions.
        """
        if not self.pdf_is_encrypted():
            logging.info("Encrypting PDF: %s", self.pdf_path)

            output_path = self._get_output_path(in_place, output, "-Encrypted")

            self.save_pike_pdf(
                output_path,
                crypt_type="encrypt",
                password=password,
                owner_password=owner_password,
            )
        else:
            logging.info("PDF already encrypted: %s", self.pdf_path)

    def decrypt(
        self,
        output: PathNoneType = None,
        in_place: bool = False,
        owner_password: str | None = None,
    ) -> None:
        """Decrypt the PDF if it is currently encrypted.

        If ``in_place`` is ``False`` (recommended), a decrypted copy is saved
        to a new file; otherwise, the original file is overwritten. If the PDF
        is not encrypted, no changes are made.

        Parameters
        ----------
        output : str | Path | None, default None
            Destination path for the decrypted PDF. Ignored if
            ``in_place=True``. If ``None``, a new file is created with
            ``"-Decrypted"`` appended to the original name.
        in_place : bool, default False
            Whether to overwrite the original file in place.
        owner_password : str | None, default None
            The owner password used to unlock and decrypt the PDF.
        """
        if owner_password is None:
            owner_password = "1234abcd"  # nosec B105

        if self.pdf_is_encrypted():
            logging.info("Decrypting PDF: %s", self.pdf_path)

            output_path = self._get_output_path(in_place, output, "-Decrypted")

            self.save_pike_pdf(output_path, crypt_type="decrypt")
        else:
            logging.info("PDF not encrypted, no changes made: %s", self.pdf_path)

    def rm(self) -> None:
        """Delete the PDF file from disk."""
        self.pdf_path.unlink()

    def mv(self, dst: PathType) -> None:
        """Move the PDF to a new location and update the internal path.

        Parameters
        ----------
        dst : str | Path
            Destination path, including the filename and ``.pdf`` extension.
        """
        dst_path = Path(str(dst))
        self.pdf_path.replace(dst_path)
        self.pdf_path = dst_path

    def cp(self, new_path: PathNoneType = None) -> Path:
        """Copy the PDF to a specified location and return its Path.

        Parameters
        ----------
        new_path : str | Path | None, optional
            Path to the new copy. If None it will be saved to the original PDF's
            path with '-copy' embedded between the stem and suffix. (Default: None).
        """
        if new_path is None:
            new_path = self.pdf_path.parent / f"{self.pdf_path.stem}-copy.pdf"
        new_path = Path(str(new_path)).resolve()
        shutil.copy(self.pdf_path, new_path)
        return new_path

    @classmethod
    def merge_pdfs(
        cls,
        pdf0_path: PathType,
        pdf1_path: PathType,
        output_path: PathType,
        add_separator: bool = False,
        separator_type: Literal["black", "blank"] = "black",
    ) -> None:
        """Merge two PDF files, placing the first file on top.

        Parameters
        ----------
        pdf0_path : str | Path
            Path to the first PDF, which will appear first in the output.
        pdf1_path : str | Path
            Path to the second PDF, which will appear after the first.
        output_path : str | Path
            Path to save the merged output PDF.
        add_separator : bool, default False
            If ``True``, insert a separator page between the PDFs.
        separator_type : {"black", "blank"}, default "black"
            Type of separator page to insert:

            * ``"black"`` : a black bar (~1 in height)
            * ``"blank"`` : a full blank page

        Raises
        ------
        ValueError
            If ``separator_type`` is not ``"black"`` or ``"blank"``.
        """
        with pikepdf.open(pdf0_path, allow_overwriting_input=True) as pdf0:
            if add_separator:
                match separator_type.lower():
                    case "black":
                        resource_file = "black_separator-636x72.pdf"
                    case "blank":
                        resource_file = "blank_page.pdf"
                    case _:
                        msg = (
                            "separator_type must be either 'black' or 'blank', "
                            f"not {separator_type!r}"
                        )
                        raise ValueError(msg)

                resource_path = Path(__file__).resolve().parent / "resources" / resource_file
                with (
                    as_file(resource_path) as sep_path,
                    pikepdf.open(sep_path) as sep_pdf,
                ):
                    pdf0.pages.extend(sep_pdf.pages)

            with pikepdf.open(pdf1_path) as pdf1:
                pdf0.pages.extend(pdf1.pages)

            pdf0.save(output_path)

    def resize(
        self,
        width: int,
        height: int,
        output_path: PathNoneType = None,
    ) -> None:
        """Resize all pages in the PDF to the specified dimensions.

        Parameters
        ----------
        width : int
            Desired page width in points (1 inch = 72 points).
        height : int
            Desired page height in points (1 inch = 72 points).
        output_path : str | Path | None, default None
            Path to save the resized PDF. If ``None``, a new file is created in
            the same directory with the name pattern
            ``{original_name}-{width}x{height}.pdf``.

        Raises
        ------
        ValueError
            If ``output_path`` is provided and does not end with ``.pdf``.
        """
        if output_path is None:
            output_path = self.pdf_path.parent / f"{self.pdf_path.stem}-{width}x{height}.pdf"
        elif not str(output_path).lower().endswith(".pdf"):
            msg = f"output_path should end in .pdf, not {output_path!r}"
            raise ValueError(msg)

        pdf_dims_array = pikepdf.Array([0, 0, width, height])
        with pikepdf.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                page.mediabox = pdf_dims_array
                page.cropbox = pdf_dims_array

            pdf.save(output_path)

    @classmethod
    def pdfs_are_duplicates(cls, pdf0_path: PathType, pdf1_path: PathType) -> bool:
        """Return whether two PDFs have identical extracted text content.

        Text is extracted using :mod:`pdfminer`. Layout, formatting, and
        metadata differences are ignored.

        Parameters
        ----------
        pdf0_path : str | Path
            Path to the first PDF file.
        pdf1_path : str | Path
            Path to the second PDF file.

        Returns
        -------
        bool
            ``True`` if the extracted text from both PDFs is identical,
            ``False`` otherwise.
        """
        return extract_text(pdf0_path) == extract_text(pdf1_path)
