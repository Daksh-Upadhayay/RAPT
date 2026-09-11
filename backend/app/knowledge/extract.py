"""Turn an uploaded help document into plain text with Markdown-style headings.

Every format ends up the same shape: paragraphs separated by blank lines, headings as
`#`/`##`/`###` lines. The chunker (chunking.py) only needs to understand that shape.
"""

import io
import re
from html.parser import HTMLParser
from pathlib import PurePath
from typing import ClassVar

from pypdf import PdfReader
from pypdf.errors import PdfReadError

SUPPORTED = {".md", ".markdown", ".txt", ".html", ".htm", ".pdf"}


class ExtractionError(ValueError):
    """The file can't be read as a help document (wrong type, broken, or no text)."""


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("The file isn't readable text (unknown encoding).")


class _HTMLText(HTMLParser):
    """Collects headings and text blocks; ignores scripts, styles and page chrome."""

    SKIP: ClassVar[frozenset[str]] = frozenset({"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "template"})
    HEADINGS: ClassVar[dict[str, int]] = {"h1": 1, "h2": 2, "h3": 3, "h4": 3, "h5": 3, "h6": 3}
    BLOCKS: ClassVar[frozenset[str]] = frozenset(
        {"p", "li", "td", "th", "dd", "dt", "blockquote", "pre", "div", "section", "article", "br", "tr"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.buffer: list[str] = []
        self.skip_depth = 0
        self.heading: int | None = None
        self.title: str | None = None
        self.in_title = False

    def _flush(self) -> None:
        text = re.sub(r"\s+", " ", "".join(self.buffer)).strip()
        self.buffer = []
        if not text:
            return
        self.lines.append(f"{'#' * self.heading} {text}" if self.heading else text)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag == "title":
            self.in_title = True
        elif tag in self.HEADINGS:
            self._flush()
            self.heading = self.HEADINGS[tag]
        elif tag in self.BLOCKS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag == "title":
            self.in_title = False
        elif tag in self.HEADINGS:
            self._flush()
            self.heading = None
        elif tag in self.BLOCKS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title = (self.title or "") + data
        elif not self.skip_depth:
            self.buffer.append(data)

    def text(self) -> str:
        self._flush()
        return "\n\n".join(self.lines)


def _from_html(data: bytes) -> tuple[str, str | None]:
    parser = _HTMLText()
    parser.feed(_decode(data))
    parser.close()
    return parser.text(), (parser.title or "").strip() or None


def _from_pdf(data: bytes) -> tuple[str, str | None]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ExtractionError("The PDF is password-protected.")
        pages = [(page.extract_text() or "") for page in reader.pages]
        title = (reader.metadata.title if reader.metadata else None) or None
    except (PdfReadError, ValueError, KeyError) as exc:
        raise ExtractionError(f"The PDF couldn't be read ({exc}).") from exc
    # PDFs carry no heading structure; paragraphs are separated by blank lines
    return "\n\n".join(p.strip() for p in pages if p.strip()), title


def _normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract(filename: str, data: bytes) -> tuple[str, str]:
    """(title, text) for a file. Raises ExtractionError when it can't be used."""
    suffix = PurePath(filename).suffix.lower()
    if suffix not in SUPPORTED:
        raise ExtractionError("Upload Markdown, text, HTML or PDF files.")
    if suffix == ".pdf":
        text, title = _from_pdf(data)
    elif suffix in {".html", ".htm"}:
        text, title = _from_html(data)
    else:
        text, title = _decode(data), None
    text = _normalise(text)
    if title is None and (first := re.match(r"#\s+(.+)", text)):
        title = first.group(1).strip()  # a Markdown document's own top heading
    if not text:
        raise ExtractionError("No text found in the file (a scanned PDF needs OCR first).")
    return (title or PurePath(filename).stem.replace("_", " ").replace("-", " ").strip() or "Untitled"), text


def from_paste(text: str) -> str:
    text = _normalise(text)
    if not text:
        raise ExtractionError("Paste some text first.")
    return text
