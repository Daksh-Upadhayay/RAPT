"""Split a help document into knowledge-base sections.

Sections follow the document's own headings, so one section answers one question.
Paragraphs under a heading are packed together up to `max_tokens`; a paragraph that is
too long on its own is split at sentences (and, failing that, at words). Each section's
title is "<document title>: <heading>", which also goes into its embedding.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Section:
    title: str
    content: str


def _split_long(paragraph: str, max_tokens: int, count: Callable[[str], int]) -> list[str]:
    """Pieces of one paragraph, each within max_tokens."""
    if count(paragraph) <= max_tokens:
        return [paragraph]
    pieces, current = [], ""
    units = SENTENCE_END.split(paragraph)
    if len(units) == 1:  # one endless sentence: fall back to words
        units = paragraph.split(" ")
    for unit in units:
        candidate = f"{current} {unit}".strip()
        if current and count(candidate) > max_tokens:
            pieces.append(current)
            current = unit
        else:
            current = candidate
    if current:
        pieces.append(current)
    # A single unit can still be too long (a huge word run); cut it by characters
    out = []
    for piece in pieces:
        while count(piece) > max_tokens and len(piece) > 1:
            cut = max(1, len(piece) * max_tokens // count(piece))
            out.append(piece[:cut])
            piece = piece[cut:].lstrip()
        if piece:
            out.append(piece)
    return out


def chunk(document_title: str, text: str, count: Callable[[str], int], max_tokens: int = 300) -> list[Section]:
    """Sections of `text` (paragraphs separated by blank lines, Markdown headings)."""
    groups: list[tuple[str | None, list[str]]] = [(None, [])]
    headings: dict[int, str] = {}
    for block in (b.strip() for b in text.split("\n\n")):
        if not block:
            continue
        lines = block.split("\n")
        match = HEADING.match(lines[0])
        if match:
            level = len(match.group(1))
            headings = {k: v for k, v in headings.items() if k < level}
            headings[level] = match.group(2)
            # The document's own title (usually its top heading) isn't repeated in the path
            path = [headings[k] for k in sorted(headings) if headings[k] != document_title]
            groups.append((" / ".join(path) or None, []))
            rest = "\n".join(lines[1:]).strip()
            if rest:
                groups[-1][1].append(rest)
        else:
            groups[-1][1].append(block)

    sections: list[Section] = []
    for heading, paragraphs in groups:
        if not paragraphs:
            continue
        title = f"{document_title}: {heading}" if heading else document_title
        current: list[str] = []
        for paragraph in paragraphs:
            for piece in _split_long(paragraph, max_tokens, count):
                if current and count("\n\n".join([*current, piece])) > max_tokens:
                    sections.append(Section(title, "\n\n".join(current)))
                    current = []
                current.append(piece)
        if current:
            sections.append(Section(title, "\n\n".join(current)))

    # A heading split into several sections gets "(part n)" so titles stay distinct
    totals: dict[str, int] = {}
    for s in sections:
        totals[s.title] = totals.get(s.title, 0) + 1
    seen: dict[str, int] = {}
    numbered = []
    for s in sections:
        if totals[s.title] > 1:
            seen[s.title] = seen.get(s.title, 0) + 1
            numbered.append(Section(f"{s.title} (part {seen[s.title]})", s.content))
        else:
            numbered.append(s)
    return numbered
