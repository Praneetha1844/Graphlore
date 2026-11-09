# ADR 0003: Bound the number of hops and the amount of search

Status: accepted

## Context

The number of paths grows roughly exponentially with hop count, and in a graph built from text a
long chain of individually plausible edges is rarely a meaningful answer. Unbounded traversal is
both slow and misleading.

## Decision

Search breadth-first with three limits: `max_hops` (default 3), `max_paths` (default 20, 10 for
answers) and `max_expansions` (default 10,000). Paths are cycle-free and returned shortest first.
When the expansion budget is hit the search returns what it has. If nothing is found within the
bound, the answer abstains and says so.

## Alternatives considered

- **Shortest path only.** Cheap, but hides alternative explanations.
- **Unbounded search.** Complete, but expensive and prone to long, weak chains.
- **Score paths by edge confidence.** Attractive, but the confidences come from simple extractors
  and are not calibrated, so a ranking would imply precision the data does not have.

## Consequences

- Answers are fast and predictable.
- Some real connections longer than the bound are not found; raise `--max-hops` deliberately.
- Partial results are possible when the expansion budget runs out and are not flagged as partial yet.
