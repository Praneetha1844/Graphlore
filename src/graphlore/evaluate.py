"""Evaluation harness: exact match on answer entities and recall of gold edges.

This module only computes the metrics. It never ships results; run it on your own graph.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from graphlore.graph import GraphStore
from graphlore.ontology import Ontology
from graphlore.qa import answer_question
from graphlore.resolver import normalise


@dataclass(frozen=True)
class QAItem:
    question: str
    answers: list[str] | None  # None when the item only checks paths
    gold_edges: list[tuple[str, str, str]]


@dataclass
class EvalSummary:
    items: int = 0
    abstained: int = 0
    exact_match_items: int = 0
    exact_match_correct: int = 0
    path_recall_values: list[float] = field(default_factory=list)

    @property
    def exact_match(self) -> float | None:
        return self.exact_match_correct / self.exact_match_items if self.exact_match_items else None

    @property
    def mean_path_recall(self) -> float | None:
        values = self.path_recall_values
        return sum(values) / len(values) if values else None


def load_qa(path: Path | str) -> list[QAItem]:
    """Read a JSON-lines file: ``{"question", "answers"?, "gold_edges"?}`` per line."""
    items: list[QAItem] = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            raw: dict[str, Any] = json.loads(line)
            if "question" not in raw:
                raise ValueError(f"line {number}: missing 'question'")
            raw_edges = raw.get("gold_edges", [])
            if any(len(e) != 3 for e in raw_edges):
                raise ValueError(f"line {number}: gold_edges must be [subject, predicate, object]")
            edges = [(str(e[0]), str(e[1]), str(e[2])) for e in raw_edges]
            items.append(QAItem(raw["question"], raw.get("answers"), edges))
    return items


def evaluate(
    items: list[QAItem], store: GraphStore, ontology: Ontology, max_hops: int = 3
) -> EvalSummary:
    summary = EvalSummary()
    for item in items:
        answer = answer_question(store, ontology, item.question, max_hops=max_hops)
        summary.items += 1
        summary.abstained += int(answer.abstained)

        if item.answers is not None:
            summary.exact_match_items += 1
            got = {normalise(n) for n in answer.answer_entities}
            summary.exact_match_correct += int(got == {normalise(a) for a in item.answers})

        if item.gold_edges:
            returned = set()
            for path in answer.paths:
                for edge in path:
                    s, o = store.entity(edge.source), store.entity(edge.target)
                    if s and o:
                        returned.add((normalise(s.name), edge.predicate, normalise(o.name)))
            gold = {(normalise(s), p, normalise(o)) for s, p, o in item.gold_edges}
            summary.path_recall_values.append(len(gold & returned) / len(gold))
    return summary
