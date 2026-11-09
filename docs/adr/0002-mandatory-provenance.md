# ADR 0002: Every edge must cite a stored chunk

Status: accepted

## Context

Extracted knowledge is only as trustworthy as the ability to check it. A graph of claims with no
sources cannot be audited, and an answer cannot be defended.

## Decision

The write path of every `GraphStore` refuses an edge that has no chunk id, or a chunk id that was
not stored first. Repeated facts add chunk ids to the same edge rather than creating duplicates.
Answers print the chunk text next to each step.

## Consequences

- Any fact can be traced to a sentence, which makes extraction errors easy to find.
- Chunks must be stored alongside the graph, increasing its size.
- Symmetric and inverse edges inherit the provenance of the fact they derive from.
- The model-based extractor additionally requires both entity strings to appear in the chunk text,
  which stops invented entities but cannot stop a wrong relation between real ones.
