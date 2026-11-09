"""Optional Neo4j implementation of ``GraphStore``.

Not exercised by the automated test suite, which has no database. It follows the same rules as
``NetworkXStore``: ontology-checked edges that cite an existing chunk. Relation names cannot be
Cypher parameters, so predicates are checked against the ontology *and* a strict pattern before
being placed in a query string. All other values are bound parameters.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from graphlore.graph import OntologyViolation, ProvenanceError, entity_id
from graphlore.models import Chunk, Edge, Entity
from graphlore.ontology import Ontology

_PREDICATE = re.compile(r"^[A-Z][A-Z_]*$")


class Neo4jStore:
    def __init__(self, ontology: Ontology, uri: str, user: str, password: str):
        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise RuntimeError("install the 'neo4j' extra to use the Neo4j store") from exc
        self.ontology = ontology
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self._driver.close()

    def _run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        with self._driver.session() as session:
            return [record.data() for record in session.run(query, **params)]

    def add_chunk(self, chunk: Chunk) -> None:
        self._run(
            "MERGE (c:Chunk {id: $id}) SET c.doc_id = $doc_id, c.text = $text, "
            "c.start = $start, c.end = $end",
            id=chunk.id, doc_id=chunk.doc_id, text=chunk.text, start=chunk.start, end=chunk.end,
        )

    def chunk(self, chunk_id: str) -> Chunk | None:
        rows = self._run("MATCH (c:Chunk {id: $id}) RETURN c", id=chunk_id)
        if not rows:
            return None
        c = rows[0]["c"]
        return Chunk(c["id"], c["doc_id"], c["text"], c["start"], c["end"])

    def add_entity(self, name: str, entity_type: str, aliases: Iterable[str] = ()) -> str:
        if entity_type not in self.ontology.entity_types:
            raise OntologyViolation(f"unknown entity type {entity_type!r}")
        key = entity_id(name, entity_type)
        existing = self.entity(key)
        merged = {a for a in aliases if a != name} | set(existing.aliases if existing else ())
        self._run(
            "MERGE (e:Entity {id: $id}) "
            "SET e.name = coalesce(e.name, $name), e.type = $type, e.aliases = $aliases",
            id=key, name=name, type=entity_type, aliases=sorted(merged),
        )
        return key

    def entity(self, entity_id: str) -> Entity | None:
        rows = self._run("MATCH (e:Entity {id: $id}) RETURN e", id=entity_id)
        if not rows:
            return None
        e = rows[0]["e"]
        return Entity(e["id"], e["name"], e["type"], tuple(e.get("aliases", [])))

    def entities(self) -> list[Entity]:
        rows = self._run("MATCH (e:Entity) RETURN e ORDER BY e.id")
        return [
            Entity(r["e"]["id"], r["e"]["name"], r["e"]["type"], tuple(r["e"].get("aliases", [])))
            for r in rows
        ]

    def add_edge(
        self,
        subject_id: str,
        predicate: str,
        object_id: str,
        chunk_id: str,
        confidence: float = 1.0,
    ) -> None:
        if self.chunk(chunk_id) is None:
            raise ProvenanceError(f"edge must cite a stored chunk, got {chunk_id!r}")
        subject, obj = self.entity(subject_id), self.entity(object_id)
        if subject is None or obj is None:
            raise OntologyViolation("both endpoints must be added before the edge")
        if not self.ontology.allows(predicate, subject.type, obj.type):
            raise OntologyViolation(f"{predicate} does not allow {subject.type} -> {obj.type}")
        spec = self.ontology.relations[predicate]
        self._put(subject_id, predicate, object_id, chunk_id, confidence)
        if spec.symmetric:
            self._put(object_id, predicate, subject_id, chunk_id, confidence)
        if spec.inverse:
            self._put(object_id, spec.inverse, subject_id, chunk_id, confidence)

    def _put(
        self, source: str, predicate: str, target: str, chunk_id: str, confidence: float
    ) -> None:
        if predicate not in self.ontology.relations or not _PREDICATE.match(predicate):
            raise OntologyViolation(f"refusing to build a query for relation {predicate!r}")
        self._run(
            "MATCH (a:Entity {id: $s}), (b:Entity {id: $o}) "
            f"MERGE (a)-[r:{predicate}]->(b) "
            "SET r.chunk_ids = CASE WHEN $c IN coalesce(r.chunk_ids, []) "
            "THEN r.chunk_ids ELSE coalesce(r.chunk_ids, []) + [$c] END, "
            "r.confidence = CASE WHEN coalesce(r.confidence, 0.0) > $conf "
            "THEN r.confidence ELSE $conf END",
            s=source, o=target, c=chunk_id, conf=confidence,
        )

    def neighbors(self, entity_id: str, relations: set[str] | None = None) -> list[Edge]:
        rows = self._run(
            "MATCH (a:Entity {id: $id})-[r]->(b:Entity) "
            "WHERE $rels IS NULL OR type(r) IN $rels "
            "RETURN b.id AS target, type(r) AS predicate, r.chunk_ids AS chunk_ids, "
            "r.confidence AS confidence ORDER BY predicate, target",
            id=entity_id, rels=sorted(relations) if relations is not None else None,
        )
        return [
            Edge(entity_id, r["predicate"], r["target"], tuple(r["chunk_ids"] or ()),
                 float(r["confidence"] or 1.0))
            for r in rows
        ]
