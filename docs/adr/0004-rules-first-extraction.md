# ADR 0004: Ship a rule-based extractor as the default

Status: accepted

## Context

Model-based extraction is flexible but non-deterministic, needs a provider, and can hallucinate. A
learner or reviewer should be able to run the whole pipeline offline and get the same graph every
time.

## Decision

The default extractor pairs gazetteer mentions inside a sentence and requires a trigger phrase from
the ontology between them. spaCy-based NER (`SpacyExtractor`) and model-based extraction
(`LLMExtractor`) are optional extras behind the same interface. Remote providers need an explicit
`--allow-remote` flag because they send document text off the machine.

## Consequences

- Deterministic, inspectable and testable without network access or large models.
- Low recall: only active-voice, same-sentence, adjacent-mention statements about known entities are
  found. Passive voice ("Helio was acquired by Northwind"), coreference and unlisted entities are
  missed.
- The gazetteer needs maintenance. Ambiguous surface forms are rejected at load time instead of being
  guessed at.
