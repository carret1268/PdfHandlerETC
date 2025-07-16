from importlib.resources import files, as_file
import logging
from pathlib import Path
import re
from typing import cast, Dict, List, Literal, Optional, Union

from colorama import Fore, init
from pdfminer.high_level import extract_text
import pikepdf

## setup type aliases
PageNumberType = Union[int, str, list[int | str], None]
PathType = Union[Path, str]
PathNoneType = Optional[PathType]


class PdfHandler:
    # setup regex for searching strings for page numbers. Handles complex strings like "1, 3, 5-9 and 12"
    _page_number_regex = re.compile(r"(?:[\s,]*|(?:\sand\s))(\d+)(?:-(\d+))?")

    def __init__(self, pdf_path: PathType):
        # Ensure that the path is to an existing pdf
        self.pdf_path = Path(str(pdf_path)).resolve()
        if self.pdf_path.suffix.lower() != ".pdf":
            raise ValueError(
                f"PDF path suffix must be '.pdf', not {self.pdf_path.suffix}"
            )
        if not self.pdf_path.exists():
            raise FileExistsError(f"No file exists at {self.pdf_path}")

    @classmethod
    def _get_page_numbers_from_str(cls, page_numbers: str) -> List[int]:
        """Parses a string of 1-indexed page numbers and returns a sorted list of unique page numbers.

        Accepts mixed formatting with commas, whitespace, "and", and ranges using hyphens.
        For example, the input string "1, 3, 5-7 and 10" will return [1, 3, 5, 6, 7, 10].

        This method does not adjust for zero-based indexing; it is up to the caller
        to subtract 1 if needed for internal PDF operations.

        Parameters
        ----------
        page_numbers : str
            A string representing page numbers to include. Acceptable formats include:
            - Single numbers (e.g., "3")
            - Comma-separated numbers (e.g., "1, 2, 3")
            - Ranges using hyphens (e.g., "4-6")
            - "and" as a delimiter (e.g., "2 and 5")
            - Mixed input (e.g., "1, 3-4 and 6")

        Returns
        -------
        list[int]
            A sorted list of unique 1-indexed page numbers (e.g., [1, 3, 4, 5, 6]).
            Returns an empty list if no valid numbers are found.
        """
        # get page number matches with regular expression
        page_number_matches = re.findall(cls._page_number_regex, page_numbers)

        # add those page numbers to our list, accounting for ranges
        page_numbers_set = set()
        for match in page_number_matches:
            # if singular page
            if match[-1] == "":
                page_numbers_set.add(int(match[0]))
                # page_numbers.append(int(match[0]))
            # else range of pages
            else:
                for page_number in range(int(match[0]), int(match[-1]) + 1):
                    # page_numbers.append(page_number)
                    page_numbers_set.add(page_number)

        # remove duplicates and ensure in order
        page_numbers_list = list(page_numbers_set)
        page_numbers_list.sort()

        return page_numbers_list

    @classmethod
    def _parse_page_numbers(cls, pages: PageNumberType) -> Optional[List[int]]:
        """Parses user-provided page numbers and returns a list of 0-indexed page indices.

        This helper method normalizes the `pages` argument to a list of integers
        representing page indices, suitable for PDF processing. Page numbers in
        user input are assumed to be **1-indexed**, and are converted to **0-indexed**
        integers internally.

        Acceptable input formats:
        - `None` to select the entire document
        - A single `int` or `str` (e.g., `3` or `"3"`)
        - A range string using a hyphen (e.g., `"5-7"`)
        - A comma-/space-/`"and"`-delimited string (e.g., `"1, 3 and 5-6"`)
        - A list of any combination of `int` and `str` (e.g., `[1, "3-4", "6 and 8"]`)

        Parameters
        ----------
        pages : PageNumberType
            Union[int, str, list[int | str], None], default None.
            The page numbers to extract. See acceptable formats above.

        Returns
        -------
        list[int] | None
            A sorted list of 0-indexed page indices if input is given, or None if `pages` is None.
        """
        # parse the page_numbers, first if string -- simple
        if type(pages) is str:
            pages_list = cls._get_page_numbers_from_str(pages)
        # now for int -- simple, just add one page
        elif type(pages) is int:
            pages_list = [pages]
        # now for list, values can be str or int
        elif type(pages) is list:
            new_pages = set()
            for page in pages:
                # handle str values
                if type(page) is str:
                    for p in cls._get_page_numbers_from_str(page):
                        new_pages.add(p)
                # otherwise the value must be int
                else:
                    new_pages.add(int(page))
            pages_list = list(new_pages)
            pages_list.sort()

        # convert page numbers to indices
        pages_r = [int(page) - 1 for page in pages_list]

        return pages_r

    def get_pdf_text(self, pages: PageNumberType = None) -> str:
        """Extracts text from a PDF, optionally from specific pages.

        Accepts flexible input for specifying page numbers. User-supplied page numbers
        are assumed to be **1-indexed**, and internally converted to **0-indexed**
        integers as required by the underlying PDF parser.

        Parameters
        ----------
        pages : PageNumberType, optional
            Pages to extract text from. If None (default), extracts the entire document.
            Acceptable formats include:
            - A single int or str (e.g., 5 or "5")
            - A range as a str (e.g., "2-4")
            - A comma/space/"and"-delimited str (e.g., "1, 3 and 5-6")
            - A list of ints and/or strs (e.g., [1, "3", "5-7"])

        Returns
        -------
        str
            The extracted text as a single string. Returns an empty string if no text is found.
        """
        # parse page numbers
        if pages is None:
            with pikepdf.open(self.pdf_path) as pdf:
                page_indices = [i for i in range(len(pdf.pages))]
        else:
            page_indices = cast(list[int], self._parse_page_numbers(pages))

        # now get the text
        pdf_text = extract_text(self.pdf_path, page_numbers=page_indices).strip()

        return pdf_text

    def word_count(self, pages: PageNumberType = None) -> int:
        """Counts the number of words in the PDF, optionally limited to specific pages.

        Uses simple regex-based tokenization to count words extracted from the PDF.
        Page numbers in the input are assumed to be **1-indexed** and are converted
        internally to **0-indexed** for processing.

        Parameters
        ----------
        pages : PageNumberType, optional
            Pages to include in the word count. If None (default), all pages are included.
            Acceptable formats include:
            - A single int or str (e.g., 5 or "5")
            - A range as a str (e.g., "2-4")
            - A comma/space/"and"-delimited str (e.g., "1, 3 and 5-6")
            - A list of ints and/or strs (e.g., [1, "3", "5-7"])

        Returns
        -------
        int
            The total number of words found on the specified pages.
        """
        text = self.get_pdf_text(pages)
        words = re.findall(r"\b\w+\b", text)

        return len(words)

    def pdf_is_encrypted(self) -> bool:
        """Checks whether the PDF is encrypted.

        Opens the PDF file using `pikepdf` and returns its encryption status.

        Returns
        -------
        bool
            True if the PDF is encrypted, False otherwise.
        """
        with pikepdf.open(self.pdf_path) as pike_doc:
            return pike_doc.is_encrypted

    def _get_output_path(
        self, in_place: bool, output: PathNoneType, suffix: str
    ) -> Path:
        """Resolves the output path for saving a modified PDF.

        Used internally by methods like `encrypt()` and `decrypt()` to determine
        whether to overwrite the original file or save a new copy.

        Parameters
        ----------
        in_place : bool
            If True, returns the original PDF path (overwrites the file in-place).
            If False, generates a new output path for the modified copy.
        output : Union[str, Path, None]
            The desired output path. Ignored if `in_place=True`.
            If None, a default path is generated by appending the `suffix` to the
            original filename (e.g., "document-Decrypted.pdf").
        suffix : str
            The suffix to append to the original filename when `output` is None.

        Returns
        -------
        Path
            The resolved path for saving the output PDF.

        Raises
        ------
        ValueError
            If `output` is provided and does not have a `.pdf` file extension.
        """

        if in_place:
            output_path = self.pdf_path
        else:
            if output is None:
                output_path = (
                    self.pdf_path.parent / self.pdf_path.stem / f"{suffix}.pdf"
                )
            else:
                output_path = Path(str(output))
                if output_path.suffix.lower() != ".pdf":
                    raise ValueError(
                        "output should either be None or be a Path like entity "
                        + f"with a '.pdf' suffix. Not {output}"
                    )

        return output_path

    def save_pike_pdf(
        self,
        output: PathNoneType,
        in_place: bool = False,
        crypt_type: str | None = None,
        password: Optional[str] = None,
        owner_password: Optional[str] = None,
        extract: bool = True,
        modify_annotation: bool = True,
        modify_assembly: bool = True,
        modify_form: bool = True,
        modify_other: bool = True,
        print_lowres: bool = True,
        print_highres: bool = True,
    ) -> None:
        """Saves the PDF to the given path with optional encryption or decryption.

        This method uses `pikepdf` to apply encryption settings or remove encryption
        from the PDF. If `crypt_type` is not specified, the file will be saved using
        the provided permission flags. By default, this behaves like a decryption operation.

        Parameters
        ----------
        output : str | Path | None
            Destination for the saved file. Ignored if `in_place=True`.
            If None, a new file is saved with the suffix "-Encrypted" or "-Decrypted"
            depending on usage.
        in_place : bool, default False
            If True, overwrites the original file. If False, creates a new file.
        crypt_type : str | None, default None
            A preset encryption mode. Must be one of:
            - "decrypt": disables encryption entirely (sets all permissions to True)
            - "encrypt": enables encryption with all permissions set to False
            - "no_copy": same as "decrypt", but with extract permission set to False
            - None: uses the individual permission arguments below
        password : str, default ""
            User password for opening the encrypted PDF. If left empty, no password is required to open.
        owner_password : str, default "1234abcd"
            Owner password used to set encryption permissions.
        extract : bool, default True
            Whether users can extract text or images (copy to clipboard).
        modify_annotation : bool, default True
            Whether users can modify annotations.
        modify_assembly : bool, default True
            Whether users can rearrange pages or merge documents.
        modify_form : bool, default True
            Whether users can fill in or edit form fields.
        modify_other : bool, default True
            Whether users can make general modifications to the document.
        print_lowres : bool, default True
            Whether users can print in low resolution.
        print_highres : bool, default True
            Whether users can print in high resolution.

        Raises
        ------
        ValueError
            If an invalid `crypt_type` is provided or if the resolved output path is invalid.
        """
        if password is None:
            password = ""  # nosec B105
        if owner_password is None:
            owner_password = "1234abcd"  # nosec B105

        output = self._get_output_path(in_place=in_place, output=output, suffix="")

        # create pikepdf.Encryption object based off crypt_type parameter
        if crypt_type is not None:
            crypt_type = crypt_type.lower().strip()
        match crypt_type:
            case "decrypt":
                pike_encryption = None
            case "encrypt":
                extract = False
                modify_annotation = False
                modify_assembly = False
                modify_form = False
                modify_other = False
                print_lowres = False
                print_highres = False
            case "no_copy":
                extract = False
            case None:
                pass
            case _:
                raise ValueError(
                    f"crypt_type must be ['encrypt', 'decrypt', 'no_copy', None], not {crypt_type}"
                )

        # if decrypting, encryption argument should be None, otherwise instantiate Encryption object
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

        # save the encrypted / decrypted file
        with pikepdf.open(self.pdf_path) as pike_doc:
            pike_doc.save(output, encryption=pike_encryption)

    def get_pdf_permissions(self) -> Dict[str, bool]:
        """Retrieves the current permission settings of the PDF.

        Returns a dictionary indicating which actions are permitted on the
        document (e.g., printing, copying, form modification). Permissions
        are only meaningful if the PDF is encrypted.

        Returns
        -------
        dict[str, bool]
            A dictionary mapping permission names to boolean values. Keys include:
            - "extract"
            - "modify_annotation"
            - "modify_assembly"
            - "modify_form"
            - "modify_other"
            - "print_lowres"
            - "print_highres"
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
        """Prints the PDF's encryption and permission status to the console.

        Displays whether the PDF is encrypted, followed by a list of permission
        flags (e.g., extract, print, modify). Output is color-coded using
        `colorama`:
        - Green for enabled permissions
        - Red for disabled permissions

        Returns
        -------
        None
        """
        init()

        print(f"Permissions for {self.pdf_path}")

        is_encrypted = self.pdf_is_encrypted()
        print(
            f"\tIs encrypted: {Fore.LIGHTRED_EX if is_encrypted else Fore.LIGHTGREEN_EX}{is_encrypted}{Fore.RESET}"
        )

        permissions_dict = self.get_pdf_permissions()
        for key, val in permissions_dict.items():
            print(
                f"\t\t{key}: {Fore.LIGHTGREEN_EX if val else Fore.LIGHTRED_EX}{val}{Fore.RESET}"
            )

    def encrypt(
        self,
        output: PathNoneType = None,
        in_place: bool = False,
        password: Optional[str] = None,
        owner_password: Optional[str] = None,
    ) -> None:
        """Encrypts the PDF if it is not already encrypted.

        Creates an encrypted version of the PDF using default restrictive permissions.
        If `in_place` is False, the encrypted file is saved to a new path; otherwise,
        it overwrites the original file. By default, encryption allows viewing the PDF
        without a password but disallows copying.

        If the file is already encrypted, no changes are made and a log message is generated.

        For fine-grained control over permissions, use `save_pike_pdf()` directly.

        Parameters
        ----------
        output : str | Path | None, default None
            Destination path for the encrypted PDF. Ignored if `in_place=True`.
            If None, a new file is created with "-Encrypted" appended to the original name.
        in_place : bool, default False
            Whether to overwrite the original file in-place.
        password : str, default ""
            The user password required to open the PDF. If empty, no password is required to view.
        owner_password : str, default "1234abcd"
            The owner password used to set encryption and permissions.

        Returns
        -------
        None
        """
        if not self.pdf_is_encrypted():
            logging.info(f"Encrypting the following PDF: {self.pdf_path}")

            ## get output path
            output_path = self._get_output_path(in_place, output, "-Encrypted")

            ## save pdf contents in encrypted path
            self.save_pike_pdf(
                output_path,
                crypt_type="encrypt",
                password=password,
                owner_password=owner_password,
            )

        else:
            logging.info(f"The following PDF was already encrypted: {self.pdf_path}")

    def decrypt(
        self,
        output: PathNoneType = None,
        in_place: bool = False,
        owner_password: Optional[str] = None,
    ) -> None:
        """Decrypts the PDF if it is currently encrypted.

        If `in_place` is False (recommended), a decrypted copy is saved to a new file;
        otherwise, the original file is overwritten. If the PDF is not encrypted,
        no changes are made and a log message is generated.

        For full control over permission settings, use `save_pike_pdf()` directly.

        Parameters
        ----------
        output : str | Path | None, default None
            Destination path for the decrypted PDF. Ignored if `in_place=True`.
            If None, a new file is created with "-Decrypted" appended to the original name.
        in_place : bool, default False
            Whether to overwrite the original file in-place.
        owner_password : str, default "1234abcd"
            The owner password used to unlock and decrypt the PDF.

        Returns
        -------
        None
        """
        if owner_password is None:
            owner_password = "1234abcd"  # nosec B105

        if self.pdf_is_encrypted():
            logging.info(f"Decrypting the following PDF: {self.pdf_path}")

            ## determine output path
            output_path = self._get_output_path(in_place, output, "-Decrypted")

            ## save pdf contents in encrypted path
            self.save_pike_pdf(output_path, crypt_type="decrypt")

        else:
            logging.info(f"The following PDF was NOT encrypted: {self.pdf_path}")

    def rm(self) -> None:
        """Deletes the PDF file from disk and clears the internal file reference.

        This method permanently removes the file at `self.pdf_path` and sets
        `self.pdf_path` to None to prevent further operations on a non-existent file.

        Returns
        -------
        None
        """
        self.pdf_path.unlink()

    def mv(self, dst: PathType) -> None:
        """Moves the PDF to a new location and updates the internal file reference.

        Renames or relocates the PDF file to the specified destination path.
        After the move, `self.pdf_path` is updated to point to the new location.

        Parameters
        ----------
        dst : str | Path
            The destination path to move the PDF to. Must include the filename and `.pdf` extension.

        Returns
        -------
        None
        """
        dst = Path(str(dst))
        self.pdf_path.replace(dst)
        self.pdf_path = dst

    @classmethod
    def merge_pdfs(
        cls,
        pdf0_path: PathType,
        pdf1_path: PathType,
        output_path: PathType,
        add_separator: bool = False,
        separator_type: Literal[
            "black", "blank"
        ] = "black",  # either 'black' or 'blank'
    ) -> None:
        """Merges two PDF files together, placing the first file on top.

        Combines `pdf0_path` and `pdf1_path` into a single document and saves the
        result to `output_path`. Optionally inserts a visual separator page between
        the two PDFs, using either a black bar or a blank page.

        This is a class method and does not depend on any instance-specific data.

        Parameters
        ----------
        pdf0_path : str | Path
            Path to the first PDF, which will appear first in the output.
        pdf1_path : str | Path
            Path to the second PDF, which will appear after the first in the output.
        output_path : str | Path
            Path to save the merged output PDF.
        add_separator : bool, default False
            If True, inserts a separator page between the PDFs.
        separator_type : Literal["black", "blank"] default "black"
            Type of separator page to insert. Must be one of:
            - "black": a black bar (~1in height)
            - "blank": a full blank page

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If `separator_type` is not "black" or "blank".
        """
        with pikepdf.open(pdf0_path, allow_overwriting_input=True) as pdf0:
            if add_separator:
                match separator_type.lower():
                    case "black":
                        resource_file = "black_separator-636x72.pdf"
                    case "blank":
                        resource_file = "blank_page.pdf"
                    case _:
                        raise ValueError(
                            "separator_type must be either 'black' or 'blank'"
                        )

                resource_path = files("pdfhelper.resources") / resource_file
                with as_file(resource_path) as sep_path:
                    with pikepdf.open(sep_path) as sep_pdf:
                        pdf0.pages.extend(sep_pdf.pages)

            with pikepdf.open(pdf1_path) as pdf1:
                pdf0.pages.extend(pdf1.pages)

            pdf0.save(output_path)

    def resize(self, width: int, height: int, output_path: PathNoneType = None) -> None:
        """Resizes all pages in the PDF to the specified dimensions.

        Sets the media box and crop box of every page to the given width and height,
        effectively standardizing the page size throughout the document.

        Parameters
        ----------
        width : int
            Desired page width in points (1 inch = 72 points).
        height : int
            Desired page height in points (1 inch = 72 points).
        output_path : str | Path | None, default None
            Path to save the resized PDF. If None, a new file is created in the same
            directory with the name pattern: `{original_name}-{width}x{height}.pdf`.

        Raises
        ------
        ValueError
            If `output_path` is provided and does not end with `.pdf`.

        Returns
        -------
        None
        """
        if output_path is None:
            output_path = (
                self.pdf_path.parent / f"{self.pdf_path.stem}-{width}x{height}.pdf"
            )
        elif not str(output_path).lower().endswith(".pdf"):
            raise ValueError(f"output_path should end in .pdf, not {output_path}")

        pdf_dims_array = pikepdf.Array([0, 0, width, height])
        with pikepdf.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                ## set the mediabox and cropbox for each page object
                page.mediabox = pdf_dims_array
                page.cropbox = pdf_dims_array

            pdf.save(output_path)

    @classmethod
    def pdfs_are_duplicates(cls, pdf0_path: PathType, pdf1_path: PathType) -> bool:
        """Checks whether two PDFs have identical extracted text content.

        Compares the text extracted from both PDF files using `pdfminer`. This method
        ignores layout, formatting, and metadata differences—only the visible textual
        content is compared.

        Parameters
        ----------
        pdf0_path : str | Path
            Path to the first PDF file.
        pdf1_path : str | Path
            Path to the second PDF file.

        Returns
        -------
        bool
            True if the extracted text from both PDFs is identical, False otherwise.
        """
        return extract_text(pdf0_path) == extract_text(pdf1_path)
