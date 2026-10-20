"""Turn a document into stable, citable chunks. Everything here is deterministic: chunk IDs and
offsets must not change between runs, because citations point at them."""
from __future__ import annotations

import re
from typing import List, Tuple

from .schemas import Chunk, Document, DocumentIn, make_chunk_id

_BLANK_RUN = re.compile(r"\n{3,}")
_PARAGRAPH = re.compile(r"[^\n]+(?:\n[^\n]+)*")
# Sentence end: . ! or ? (plus closing quotes/brackets) followed by whitespace, unless the next word is
# lowercase or the period closes a known abbreviation. A rule of thumb, not a parser: an unlisted
# abbreviation before a capital letter still ends a sentence, which only cuts a long paragraph early.
_SENTENCE_END = re.compile(r"([.!?][\"')\]]*)\s+")
_WORD_BEFORE = re.compile(r"[A-Za-z]+$")
_ABBREVIATIONS = frozenset({"dr", "mr", "mrs", "ms", "prof", "sec", "fig", "vs"})


def normalize_text(text: str) -> str:
    """Unify line endings, strip trailing spaces and tabs, collapse blank-line runs.

    Wording is untouched: other Unicode whitespace (such as a non-breaking space) is kept.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip(" \t") for line in text.split("\n"))
    return _BLANK_RUN.sub("\n\n", text)


def _ends_sentence(text: str, match: re.Match) -> bool:
    # text[match.end()] exists: paragraphs are stripped, so a match never reaches the end of one.
    if text[match.end()].islower():
        return False
    if match.group(1) == ".":
        # look back at most 10 characters: the longest listed abbreviation has 4 letters
        word = _WORD_BEFORE.search(text, max(0, match.start() - 10), match.start())
        if word and word.group().lower() in _ABBREVIATIONS:
            return False
    return True


def _units(text: str, max_chars: int) -> List[Tuple[int, int]]:
    """Spans of whole paragraphs, or of sentences for a paragraph longer than max_chars."""
    spans = []
    for paragraph in _PARAGRAPH.finditer(text):
        raw = paragraph.group()
        start = paragraph.start() + len(raw) - len(raw.lstrip())
        end = paragraph.start() + len(raw.rstrip())
        if start >= end:
            continue
        if end - start <= max_chars:
            spans.append((start, end))
            continue
        position = start
        for sentence in _SENTENCE_END.finditer(text, start, end):
            if not _ends_sentence(text, sentence):
                continue
            spans.append((position, sentence.end(1)))
            position = sentence.end()
        if position < end:
            spans.append((position, end))
    return spans


def ingest_document(doc_in: DocumentIn, max_chars: int = 800) -> Tuple[Document, List[Chunk]]:
    """Build the Document to store (with its content hash) and its chunks.

    The hash is the SHA-256 of the raw content, exactly as uploaded: a file that differs only in line
    endings or trailing spaces gets a different hash. A hash supplied by the caller is ignored and
    recomputed. The result is a plain Document, whatever subclass of DocumentIn came in.
    """
    doc = Document(**doc_in.model_dump(exclude={"content_hash"}))
    return doc, chunk_document(doc, max_chars)


def chunk_document(doc: Document, max_chars: int = 800) -> List[Chunk]:
    """Split a document into chunks of at most max_chars, unless a single sentence is longer.

    Offsets are positions in normalize_text(doc.content), and text[start_offset:end_offset] is the
    chunk's text exactly.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be at least 1")
    text = normalize_text(doc.content)
    merged = []
    for start, end in _units(text, max_chars):
        if merged and end - merged[-1][0] <= max_chars:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return [
        Chunk(
            chunk_id=make_chunk_id(doc.document_id, index),
            document_id=doc.document_id,
            index=index,
            text=text[start:end],
            start_offset=start,
            end_offset=end,
        )
        for index, (start, end) in enumerate(merged)
    ]
