"""Read and write graphs as JSON (lossless) or GraphML (for visualisation tools)."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from graphlore.graph import NetworkXStore
from graphlore.ontology import Ontology


def write_json(store: NetworkXStore, path: Path | str) -> None:
    Path(path).write_text(json.dumps(store.to_dict(), indent=2, ensure_ascii=False), "utf-8")


def load_json(path: Path | str, ontology: Ontology) -> NetworkXStore:
    """Load a graph written by ``write_json``; every edge is re-validated on load."""
    return NetworkXStore.from_dict(ontology, json.loads(Path(path).read_text("utf-8")))


def write_graphml(store: NetworkXStore, path: Path | str) -> None:
    """GraphML cannot hold lists, so aliases and chunk ids are joined with ``;``."""
    graph = nx.MultiDiGraph()
    for entity in store.entities():
        graph.add_node(
            entity.id, name=entity.name, type=entity.type, aliases=";".join(entity.aliases)
        )
    for edge in store.edges():
        graph.add_edge(
            edge.source,
            edge.target,
            key=edge.predicate,
            predicate=edge.predicate,
            chunk_ids=";".join(edge.chunk_ids),
            confidence=edge.confidence,
        )
    nx.write_graphml(graph, str(path))
