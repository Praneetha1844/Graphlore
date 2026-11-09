"""Sentence-aware chunking with sentence overlap and character offsets."""

from __future__ import annotations

import re

from graphlore.models import Chunk, Document

# A sentence ends at . ! or ? followed by whitespace and a capital letter, digit or quote.
# Abbreviations such as "Dr. Okafor" can be split wrongly; see the README limitations.
_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    position = 0
    for match in _BOUNDARY.finditer(text):
        spans.append((position, match.start()))
        position = match.end()
    spans.append((position, len(text)))
    return [(s, e) for s, e in spans if text[s:e].strip()]


def chunk_document(document: Document, max_chars: int = 500, overlap: int = 1) -> list[Chunk]:
    """Group consecutive sentences into chunks of at most ``max_chars`` characters.

    A single sentence longer than ``max_chars`` becomes its own chunk. ``overlap`` sentences
    from the end of one chunk are repeated at the start of the next.
    """
    if max_chars < 50:
        raise ValueError("max_chars must be at least 50")
    if overlap < 0:
        raise ValueError("overlap must not be negative")

    text = document.text
    chunks: list[Chunk] = []
    window: list[tuple[int, int]] = []

    def flush() -> None:
        start, end = window[0][0], window[-1][1]
        chunk_id = f"{document.id}:{len(chunks)}"
        chunks.append(Chunk(chunk_id, document.id, text[start:end], start, end))

    for span in sentence_spans(text):
        if window and span[1] - window[0][0] > max_chars:
            flush()
            window = window[-overlap:] if overlap else []
            while window and span[1] - window[0][0] > max_chars:
                window.pop(0)
        window.append(span)
    if window:
        flush()
    return chunks
