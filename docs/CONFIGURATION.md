# Configuration reference

## Files

| File | Purpose |
| --- | --- |
| `ontology/default.yaml` | Entity types and typed relations. See below. |
| `ontology/gazetteer.yaml` | Known entities and aliases for the rule-based extractor. |
| `eval/qa.jsonl` | Question file for `graphlore eval`. |

### Ontology

```yaml
entity_types: [Person, Organization, Location]
relations:
  WORKS_AT:
    domain: [Person]          # allowed subject types
    range: [Organization]     # allowed object types
    triggers: [works at]      # phrases between two mentions in text
    cues: [work, employer]    # words in a question that suggest this relation
    inverse: EMPLOYS          # stored automatically in the opposite direction
```

- Relation names are `UPPER_SNAKE_CASE`.
- Every type used in a `domain` or `range` must be declared in `entity_types`.
- `symmetric: true` needs equal `domain` and `range`.
- An `inverse` must exist and swap the domain and range.
- **Order matters:** when several triggers fit the text between two mentions, the first relation
  listed whose types fit wins.
- A relation with no `triggers` is never extracted from text; it only appears as an inverse or
  through the model-based extractor.

### Gazetteer

```yaml
entities:
  - { name: Mira Okafor, type: Person, aliases: [Mira] }
```

A surface form (name or alias, case-insensitive) that belongs to two different entities is an
error. Types must be declared in the ontology.

## Environment variables

| Variable | Default | Used by |
| --- | --- | --- |
| `GRAPHLORE_ONTOLOGY` | `ontology/default.yaml` | Default for `--ontology`. The container image sets it. |
| `GRAPHLORE_GAZETTEER` | `ontology/gazetteer.yaml` | Default for `build --gazetteer`. The container image sets it. |
| `OLLAMA_HOST` | `http://localhost:11434` | `--provider ollama` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | `--provider openai`. Must be `https`, or `http` on `localhost` / `127.0.0.1`. |
| `OPENAI_API_KEY` | none | `--provider openai` |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | none | Listed in `.env.example` for your own code that constructs `Neo4jStore`. The CLI does not read them. |

Graphlore does not load `.env` files; export variables in your shell.

## Tunable values

| Value | Default | Where |
| --- | --- | --- |
| Chunk size / overlap | 500 characters / 1 sentence | `build --max-chars`, `--overlap` |
| Maximum hops / paths | 3 / 10 | `query --max-hops`, `--max-paths` |
| Search work limit | 10,000 edge expansions | `qa.find_paths(max_expansions=...)` |
| Automatic name merge threshold | similarity 0.92 | `resolver.MERGE_THRESHOLD` |
| Reported-not-merged band | 0.80 to 0.92 | `resolver.REVIEW_THRESHOLD` |
| Citation quote length | 200 characters | `qa.answer_question` |
| Provider request timeout | 120 seconds | `llm.py` |

The similarity thresholds are untuned starting points.
