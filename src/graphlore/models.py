"""Plain data carriers shared by the pipeline."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    id: str
    text: str


@dataclass(frozen=True)
class Chunk:
    id: str
    doc_id: str
    text: str
    start: int  # character offsets into the source document
    end: int


@dataclass(frozen=True)
class Triple:
    """One extracted statement, always tied to the chunk it came from."""

    subject: str
    subject_type: str
    predicate: str
    object: str
    object_type: str
    chunk_id: str
    confidence: float = 1.0


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    type: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Edge:
    source: str
    predicate: str
    target: str
    chunk_ids: tuple[str, ...]
    confidence: float = 1.0
