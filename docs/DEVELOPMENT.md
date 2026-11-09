# Local development

Requires Python 3.12 or newer.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
make install                       # editable install with dev tools
pre-commit install                 # optional
make check                         # ruff, mypy (strict) and pytest with coverage
```

Optional extras: `pip install -e ".[spacy]"` (also download a spaCy model), `".[neo4j]"`,
`".[pdf]"`.

## Layout

- `src/graphlore/` is the package. `graph.py` defines the `GraphStore` protocol that
  `NetworkXStore` and `Neo4jStore` implement; `qa.py` only depends on the protocol.
- `ontology/`, `examples/` and `eval/` hold the hand-written, fictional sample data used by the
  tests (see `tests/conftest.py`).
- `docs/adr/` holds decision records; add one when a choice has real trade-offs.

## Conventions

- Type hints everywhere; `mypy --strict` runs on `src`.
- Line length 100, `ruff` for lint and format.
- Every write path goes through the store, which enforces ontology typing and provenance. Do not
  add a way to create an edge without a chunk.
- Model providers implement `complete(system, prompt) -> str`; use `FakeProvider` in tests.
- Treat model output as untrusted: validate it, and require it to be grounded in the chunk.

## Adding an extractor

1. Implement `extract(chunk: Chunk) -> list[Triple]`; set `chunk_id` on every triple.
2. Do not enforce the ontology yourself; `build_graph` and the store do that. Count what you drop.
3. Add it to `_extractor` in `cli.py` and describe its limits in the README.
4. Test it with hand-written chunks. Never put real or private text in the tests.

## Adding a relation to the sample ontology

Add it to `ontology/default.yaml` (order matters for triggers), then extend the gazetteer and the
sample corpus, and add a question to `eval/qa.jsonl` if it should be evaluated. The loader
rejects an inconsistent ontology with a message naming the relation.
