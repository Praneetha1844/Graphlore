"""Question answering over the graph: link entities, retrieve bounded paths, cite chunks.

There is no free-text generation here. Answers are assembled from stored paths, and every
edge in an answer is listed with the chunk that supports it.
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field

from graphlore.graph import GraphStore
from graphlore.llm import LLMError, LLMProvider
from graphlore.models import Edge, Entity
from graphlore.ontology import Ontology

Path = tuple[Edge, ...]


@dataclass(frozen=True)
class Citation:
    number: int
    chunk_id: str
    quote: str


@dataclass
class Answer:
    question: str
    text: str
    paths: list[Path] = field(default_factory=list)
    answer_entities: list[str] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    linked: list[str] = field(default_factory=list)
    abstained: bool = False


def _squash(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def link_entities(store: GraphStore, question: str) -> list[Entity]:
    """Find graph entities mentioned in a question (names and aliases, longest match first,
    non-overlapping), returned in order of appearance. Exact matching only."""
    text = _squash(question)
    candidates: list[tuple[str, Entity]] = []
    for entity in store.entities():
        for surface in {entity.name, *entity.aliases}:
            squashed = _squash(surface)
            if squashed:
                candidates.append((squashed, entity))
    candidates.sort(key=lambda c: (-len(c[0]), c[0], c[1].id))

    taken: list[tuple[int, int]] = []
    found: dict[str, tuple[int, Entity]] = {}
    for surface, entity in candidates:
        if entity.id in found:
            continue
        for match in re.finditer(rf"(?<![a-z0-9]){re.escape(surface)}(?![a-z0-9])", text):
            span = match.span()
            if all(span[1] <= a or span[0] >= b for a, b in taken):
                taken.append(span)
                found[entity.id] = (span[0], entity)
                break
    return [entity for _, entity in sorted(found.values(), key=lambda item: item[0])]


def find_paths(
    store: GraphStore,
    source_id: str,
    *,
    max_hops: int = 3,
    relations: set[str] | None = None,
    target_id: str | None = None,
    max_paths: int = 20,
    max_expansions: int = 10_000,
) -> list[Path]:
    """Breadth-first, cycle-free paths of at most ``max_hops`` edges, shortest first.

    With ``target_id`` only paths that end there are returned and they are not extended past
    it. ``max_paths`` and ``max_expansions`` bound the work; hitting the latter returns what was
    found so far.
    """
    if max_hops < 1 or max_paths < 1:
        raise ValueError("max_hops and max_paths must be at least 1")
    results: list[Path] = []
    queue: deque[tuple[str, Path]] = deque([(source_id, ())])
    expansions = 0
    while queue and len(results) < max_paths:
        node, path = queue.popleft()
        if len(path) >= max_hops:
            continue
        visited = {source_id, *(e.target for e in path)}
        for edge in store.neighbors(node, relations):
            expansions += 1
            if expansions > max_expansions:
                return results
            if edge.target in visited:
                continue
            extended = (*path, edge)
            if target_id is None:
                results.append(extended)
                queue.append((edge.target, extended))
            elif edge.target == target_id:
                results.append(extended)
            else:
                queue.append((edge.target, extended))
            if len(results) >= max_paths:
                break
    return results


def _name(store: GraphStore, entity_id: str) -> str:
    entity = store.entity(entity_id)
    return entity.name if entity else entity_id


def _render_path(store: GraphStore, path: Path, numbers: dict[str, int]) -> str:
    parts = [_name(store, path[0].source)]
    for edge in path:
        cites = ",".join(str(numbers[c]) for c in edge.chunk_ids)
        parts.append(f"-[{edge.predicate}]-> {_name(store, edge.target)} [{cites}]")
    return " ".join(parts)


def _abstain(question: str, reason: str, linked: list[str] | None = None) -> Answer:
    return Answer(question, reason, linked=linked or [], abstained=True)


def answer_question(
    store: GraphStore,
    ontology: Ontology,
    question: str,
    max_hops: int = 3,
    max_paths: int = 10,
) -> Answer:
    """Answer from graph evidence, or abstain.

    - Two or more linked entities: return paths from the first to each of the others.
    - One linked entity: expand from it. If the question contains relation cue words from the
      ontology, only those relations are followed (on every hop); otherwise all are.
    """
    linked = link_entities(store, question)
    names = [e.name for e in linked]
    if not linked:
        return _abstain(question, "No entity in the question matches the graph.")

    paths: list[Path] = []
    if len(linked) >= 2:
        for other in linked[1:]:
            paths += find_paths(
                store, linked[0].id, max_hops=max_hops, target_id=other.id, max_paths=max_paths
            )
    else:
        hints = ontology.predicates_for_question(question) or None
        paths = find_paths(
            store, linked[0].id, max_hops=max_hops, relations=hints, max_paths=max_paths
        )
    if not paths:
        return _abstain(question, f"No supported answer within {max_hops} hop(s).", names)

    numbers: dict[str, int] = {}
    for path in paths:
        for edge in path:
            for chunk_id in edge.chunk_ids:
                numbers.setdefault(chunk_id, len(numbers) + 1)
    citations = []
    for chunk_id, number in numbers.items():
        chunk = store.chunk(chunk_id)
        quote = " ".join(chunk.text.split())[:200] if chunk else "(chunk missing)"
        citations.append(Citation(number, chunk_id, quote))

    ends = list(dict.fromkeys(_name(store, p[-1].target) for p in paths))
    lines = ["Answer from graph evidence:"]
    lines += [f"{i}. {_render_path(store, p, numbers)}" for i, p in enumerate(paths, 1)]
    lines += ["Sources:"] + [f'[{c.number}] {c.chunk_id}: "{c.quote}"' for c in citations]
    return Answer(question, "\n".join(lines), paths, ends, citations, names)


def phrase_answer(answer: Answer, provider: LLMProvider) -> str:
    """Optionally rewrite the evidence as a sentence. Falls back to the deterministic text if the
    provider fails or its reply mentions none of the answer entities. This is a weak check: it
    does not prove the sentence adds no unsupported claim."""
    if answer.abstained:
        return answer.text
    try:
        reply = provider.complete(
            "Rewrite the evidence as one short answer. Use only the facts given; add nothing.",
            f"Question: {answer.question}\n{answer.text}",
        ).strip()
    except LLMError:
        return answer.text
    if reply and any(name.lower() in reply.lower() for name in answer.answer_entities):
        return f"{reply}\n\n{answer.text}"
    return answer.text
