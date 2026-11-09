"""Entity resolution: normalisation plus fuzzy matching, with documented thresholds.

Names are only ever merged within one entity type. Two names merge automatically when their
normalised forms are equal or their similarity ratio reaches ``MERGE_THRESHOLD``. Pairs between
``REVIEW_THRESHOLD`` and ``MERGE_THRESHOLD`` are reported for a person to look at, not merged.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from difflib import SequenceMatcher

MERGE_THRESHOLD = 0.92
REVIEW_THRESHOLD = 0.80
_SUFFIXES = {"inc", "ltd", "llc", "corp", "corporation", "gmbh", "co", "company", "plc", "sa", "ag"}


def normalise(name: str) -> str:
    """Lower-case, strip punctuation, collapse spaces and drop trailing company suffixes."""
    tokens = re.sub(r"[^\w\s]", " ", name.lower()).split()
    while len(tokens) > 1 and tokens[-1] in _SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


@dataclass
class Resolution:
    canonical: dict[tuple[str, str], str] = field(default_factory=dict)  # (type, raw) -> name
    possible_duplicates: list[tuple[str, str, str, float]] = field(default_factory=list)

    def resolve(self, entity_type: str, raw: str) -> str:
        return self.canonical[(entity_type, raw)]


def resolve_entities(mentions: Iterable[tuple[str, str]]) -> Resolution:
    """Cluster ``(name, type)`` mentions. The canonical name of a cluster is its most frequent
    surface form (ties: longest, then alphabetical). Comparison is quadratic in the number of
    distinct names per type, which is fine for thousands of entities, not millions."""
    counts: Counter[tuple[str, str]] = Counter(mentions)
    result = Resolution()
    by_type: dict[str, list[str]] = {}
    for (name, etype), _ in sorted(counts.items()):
        by_type.setdefault(etype, []).append(name)

    for etype, names in by_type.items():
        parent = {n: n for n in names}

        def find(x: str, parent: dict[str, str] = parent) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        norms = {n: normalise(n) for n in names}
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                score = 1.0 if norms[a] == norms[b] else similarity(norms[a], norms[b])
                if score >= MERGE_THRESHOLD:
                    parent[find(a)] = find(b)
                elif score >= REVIEW_THRESHOLD:
                    result.possible_duplicates.append((etype, a, b, round(score, 3)))

        clusters: dict[str, list[str]] = {}
        for name in names:
            clusters.setdefault(find(name), []).append(name)
        for members in clusters.values():
            best = min(members, key=lambda n: (-counts[(n, etype)], -len(n), n))
            for member in members:
                result.canonical[(etype, member)] = best
    return result
