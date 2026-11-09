"""Graph store interface and the in-memory NetworkX implementation.

Two rules are enforced on every write: an edge must satisfy the ontology, and it must cite a
chunk that exists. A fact with no source cannot be stored.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Protocol

import networkx as nx

from graphlore.models import Chunk, Edge, Entity
from graphlore.ontology import Ontology


class OntologyViolation(ValueError):
    """An entity type or relation is not allowed by the ontology."""


class ProvenanceError(ValueError):
    """An edge cites no chunk, or a chunk that was never stored."""


def entity_id(name: str, entity_type: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "unnamed"
    return f"{entity_type.lower()}:{slug}"


class GraphStore(Protocol):
    def add_chunk(self, chunk: Chunk) -> None: ...

    def add_entity(self, name: str, entity_type: str, aliases: Iterable[str] = ()) -> str: ...

    def add_edge(
        self,
        subject_id: str,
        predicate: str,
        object_id: str,
        chunk_id: str,
        confidence: float = 1.0,
    ) -> None: ...

    def entity(self, entity_id: str) -> Entity | None: ...

    def entities(self) -> list[Entity]: ...

    def neighbors(self, entity_id: str, relations: set[str] | None = None) -> list[Edge]: ...

    def chunk(self, chunk_id: str) -> Chunk | None: ...


class NetworkXStore:
    """In-memory store. Symmetric relations are stored in both directions and declared inverse
    relations are materialised, so traversal only ever follows outgoing edges."""

    def __init__(self, ontology: Ontology):
        self.ontology = ontology
        self.graph = nx.MultiDiGraph()
        self._chunks: dict[str, Chunk] = {}

    def add_chunk(self, chunk: Chunk) -> None:
        self._chunks[chunk.id] = chunk

    def chunk(self, chunk_id: str) -> Chunk | None:
        return self._chunks.get(chunk_id)

    def chunks(self) -> list[Chunk]:
        return [self._chunks[k] for k in sorted(self._chunks)]

    def add_entity(self, name: str, entity_type: str, aliases: Iterable[str] = ()) -> str:
        if entity_type not in self.ontology.entity_types:
            raise OntologyViolation(f"unknown entity type {entity_type!r}")
        key = entity_id(name, entity_type)
        extra = {a for a in aliases if a != name}
        if key in self.graph:
            extra |= set(self.graph.nodes[key]["aliases"])
        else:
            self.graph.add_node(key, name=name, type=entity_type, aliases=())
        self.graph.nodes[key]["aliases"] = tuple(sorted(extra))
        return key

    def entity(self, entity_id: str) -> Entity | None:
        if entity_id not in self.graph:
            return None
        data = self.graph.nodes[entity_id]
        return Entity(entity_id, data["name"], data["type"], tuple(data["aliases"]))

    def entities(self) -> list[Entity]:
        found = (self.entity(n) for n in sorted(self.graph.nodes))
        return [e for e in found if e is not None]

    def add_edge(
        self,
        subject_id: str,
        predicate: str,
        object_id: str,
        chunk_id: str,
        confidence: float = 1.0,
    ) -> None:
        if not chunk_id or chunk_id not in self._chunks:
            raise ProvenanceError(f"edge must cite a stored chunk, got {chunk_id!r}")
        subject, obj = self.entity(subject_id), self.entity(object_id)
        if subject is None or obj is None:
            raise OntologyViolation("both endpoints must be added before the edge")
        if not self.ontology.allows(predicate, subject.type, obj.type):
            raise OntologyViolation(
                f"{predicate} does not allow {subject.type} -> {obj.type}"
            )
        spec = self.ontology.relations[predicate]
        self._put(subject_id, predicate, object_id, chunk_id, confidence)
        if spec.symmetric:
            self._put(object_id, predicate, subject_id, chunk_id, confidence)
        if spec.inverse:
            self._put(object_id, spec.inverse, subject_id, chunk_id, confidence)

    def _put(
        self, source: str, predicate: str, target: str, chunk_id: str, confidence: float
    ) -> None:
        if self.graph.has_edge(source, target, key=predicate):
            data = self.graph.edges[source, target, predicate]
            if chunk_id not in data["chunk_ids"]:
                data["chunk_ids"] = (*data["chunk_ids"], chunk_id)
            data["confidence"] = max(data["confidence"], confidence)
        else:
            self.graph.add_edge(
                source, target, key=predicate, chunk_ids=(chunk_id,), confidence=confidence
            )

    def edges(self) -> list[Edge]:
        return sorted(
            (
                Edge(u, k, v, tuple(d["chunk_ids"]), d["confidence"])
                for u, v, k, d in self.graph.edges(keys=True, data=True)
            ),
            key=lambda e: (e.source, e.predicate, e.target),
        )

    def neighbors(self, entity_id: str, relations: set[str] | None = None) -> list[Edge]:
        if entity_id not in self.graph:
            return []
        return [
            e for e in self.edges_from(entity_id) if relations is None or e.predicate in relations
        ]

    def edges_from(self, entity_id: str) -> list[Edge]:
        return sorted(
            (
                Edge(entity_id, k, v, tuple(d["chunk_ids"]), d["confidence"])
                for _, v, k, d in self.graph.out_edges(entity_id, keys=True, data=True)
            ),
            key=lambda e: (e.predicate, e.target),
        )

    # ---- serialisation

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [
                {"id": e.id, "name": e.name, "type": e.type, "aliases": list(e.aliases)}
                for e in self.entities()
            ],
            "edges": [
                {
                    "source": e.source,
                    "predicate": e.predicate,
                    "target": e.target,
                    "chunk_ids": list(e.chunk_ids),
                    "confidence": e.confidence,
                }
                for e in self.edges()
            ],
            "chunks": [
                {"id": c.id, "doc_id": c.doc_id, "text": c.text, "start": c.start, "end": c.end}
                for c in self.chunks()
            ],
        }

    @classmethod
    def from_dict(cls, ontology: Ontology, data: dict[str, Any]) -> NetworkXStore:
        """Rebuild a store, re-validating every entity and edge against the ontology."""
        store = cls(ontology)
        for c in data["chunks"]:
            store.add_chunk(Chunk(c["id"], c["doc_id"], c["text"], c["start"], c["end"]))
        for e in data["entities"]:
            store.add_entity(e["name"], e["type"], e["aliases"])
        for edge in data["edges"]:
            for chunk_id in edge["chunk_ids"]:
                store.add_edge(
                    edge["source"], edge["predicate"], edge["target"], chunk_id, edge["confidence"]
                )
        return store
