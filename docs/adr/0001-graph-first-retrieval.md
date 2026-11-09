# ADR 0001: Graph-first retrieval instead of vector retrieval

Status: accepted

## Context

Retrieval-augmented generation usually embeds chunks and returns the nearest ones. That is good for
fuzzy topical lookup, but it has weak spots for questions about relationships: it cannot follow a
chain such as person, employer, headquarters, country; it cannot say that nothing supports an
answer; and its notion of "relevant" is a similarity score, not a statement that can be checked.

## Decision

Represent extracted facts as typed edges and answer by retrieving paths. Each edge points back to
its source chunk, so every step of an answer can be shown and verified. A model is optional and only
rephrases evidence that was already retrieved.

## Alternatives considered

- **Vector RAG.** Simpler to build, robust to phrasing, no extraction step. Gives no multi-hop
  structure or abstention guarantee.
- **Hybrid.** Use embeddings for entity linking and graph traversal for reasoning. A sensible next
  step, listed on the roadmap, but it adds an embedding model and a second index.

## Consequences

- Questions that name known entities and relations work well; open-ended questions do not.
- Quality is bounded by extraction. Facts the extractor misses are invisible to queries.
- Entity linking is exact on normalised names, so paraphrased entity mentions are missed.
