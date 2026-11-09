"""The ontology: which entity types and typed relations a graph may contain."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

_PREDICATE = re.compile(r"^[A-Z][A-Z_]*$")


def phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Match ``phrase`` as whole words, case-insensitively."""
    return re.compile(rf"(?<!\w){re.escape(phrase.lower())}(?!\w)", re.IGNORECASE)


class RelationSpec(BaseModel):
    domain: list[str] = Field(min_length=1)
    range: list[str] = Field(min_length=1)
    triggers: list[str] = Field(default_factory=list)  # phrases between two mentions in text
    cues: list[str] = Field(default_factory=list)  # words in a question that suggest it
    symmetric: bool = False
    inverse: str | None = None


class Ontology(BaseModel):
    entity_types: list[str] = Field(min_length=1)
    relations: dict[str, RelationSpec]

    @model_validator(mode="after")
    def _consistent(self) -> Ontology:
        types = set(self.entity_types)
        for name, spec in self.relations.items():
            if not _PREDICATE.match(name):
                raise ValueError(f"relation name {name!r} must be UPPER_SNAKE_CASE")
            unknown = (set(spec.domain) | set(spec.range)) - types
            if unknown:
                raise ValueError(f"{name} uses undeclared entity types {sorted(unknown)}")
            if spec.symmetric and set(spec.domain) != set(spec.range):
                raise ValueError(f"symmetric relation {name} needs equal domain and range")
            if spec.inverse is not None:
                other = self.relations.get(spec.inverse)
                if other is None:
                    raise ValueError(f"{name} declares unknown inverse {spec.inverse!r}")
                if set(other.domain) != set(spec.range) or set(other.range) != set(spec.domain):
                    raise ValueError(f"inverse {spec.inverse} must swap domain and range of {name}")
        return self

    def allows(self, predicate: str, subject_type: str, object_type: str) -> bool:
        spec = self.relations.get(predicate)
        return spec is not None and subject_type in spec.domain and object_type in spec.range

    def match_trigger(self, between: str, subject_type: str, object_type: str) -> str | None:
        """First relation (in ontology order) whose trigger appears in ``between`` and whose
        types fit. Order in the YAML file is therefore significant."""
        for name, spec in self.relations.items():
            if not self.allows(name, subject_type, object_type):
                continue
            if any(phrase_pattern(t).search(between) for t in spec.triggers):
                return name
        return None

    def predicates_for_question(self, question: str) -> set[str]:
        """Relations whose cue words appear in a question; empty means no hint."""
        return {
            name
            for name, spec in self.relations.items()
            if any(phrase_pattern(cue).search(question) for cue in spec.cues)
        }


def load_ontology(path: Path | str) -> Ontology:
    with open(path, encoding="utf-8") as handle:
        return Ontology.model_validate(yaml.safe_load(handle))
