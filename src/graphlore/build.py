"""Build a graph: chunk, extract, validate, resolve entities, store with provenance."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from graphlore.chunker import chunk_document
from graphlore.extract import Extractor
from graphlore.graph import GraphStore
from graphlore.models import Document, Triple
from graphlore.ontology import Ontology
from graphlore.resolver import resolve_entities


@dataclass(frozen=True)
class BuildStats:
    documents: int
    chunks: int
    triples: int
    rejected: int
    entities: int
    edges: int
    possible_duplicates: list[tuple[str, str, str, float]] = field(default_factory=list)


def _acceptable(triple: Triple, ontology: Ontology) -> bool:
    return bool(
        triple.subject.strip()
        and triple.object.strip()
        and ontology.allows(triple.predicate, triple.subject_type, triple.object_type)
    )


def build_graph(
    documents: Iterable[Document],
    extractor: Extractor,
    store: GraphStore,
    ontology: Ontology,
    max_chars: int = 500,
    overlap: int = 1,
    known_aliases: dict[tuple[str, str], set[str]] | None = None,
) -> BuildStats:
    """Every stored edge cites the chunk its triple came from. Triples the ontology rejects,
    and self-loops created by entity resolution, are counted in ``rejected`` and dropped.

    ``known_aliases`` maps ``(canonical name, type)`` to extra surface forms, for example from
    a gazetteer. They are stored on the entity so questions can use them."""
    docs = list(documents)
    chunks = [c for d in docs for c in chunk_document(d, max_chars, overlap)]
    for chunk in chunks:
        store.add_chunk(chunk)

    accepted: list[Triple] = []
    rejected = 0
    for chunk in chunks:
        for triple in extractor.extract(chunk):
            if _acceptable(triple, ontology):
                accepted.append(triple)
            else:
                rejected += 1

    resolution = resolve_entities(
        [(t.subject, t.subject_type) for t in accepted]
        + [(t.object, t.object_type) for t in accepted]
    )
    aliases: dict[tuple[str, str], set[str]] = defaultdict(set)
    for key, surfaces in (known_aliases or {}).items():
        aliases[key] |= surfaces
    for (entity_type, raw), canonical in resolution.canonical.items():
        if raw != canonical:
            aliases[(canonical, entity_type)].add(raw)

    edges: set[tuple[str, str, str]] = set()
    for triple in accepted:
        subject = resolution.resolve(triple.subject_type, triple.subject)
        obj = resolution.resolve(triple.object_type, triple.object)
        subject_aliases = aliases[(subject, triple.subject_type)]
        object_aliases = aliases[(obj, triple.object_type)]
        subject_id = store.add_entity(subject, triple.subject_type, subject_aliases)
        object_id = store.add_entity(obj, triple.object_type, object_aliases)
        if subject_id == object_id:
            rejected += 1
            continue
        store.add_edge(subject_id, triple.predicate, object_id, triple.chunk_id, triple.confidence)
        edges.add((subject_id, triple.predicate, object_id))

    return BuildStats(
        documents=len(docs),
        chunks=len(chunks),
        triples=len(accepted),
        rejected=rejected,
        entities=len(store.entities()),
        edges=len(edges),
        possible_duplicates=resolution.possible_duplicates,
    )
