# Knowledge model

A formal description of what a Graphlore graph may contain and what follows from it. The rules
below are enforced in code (`ontology.py`, `graph.py`, `qa.py`).

## 1. Definitions

Let the ontology be a tuple **O = (T, R)**:

- **T** is a finite set of entity types, for example `{Person, Organization, Location, Technology}`.
- **R** is a finite set of relation names. Each `r` in R has a *domain* `dom(r)` and a *range*
  `ran(r)`, both non-empty subsets of T, plus optional flags `symmetric(r)` and `inverse(r)`.

A graph **G = (E, V, C, P)** consists of:

- **E**: entities, each a pair `(name, type)` with `type` in T. An entity id is derived from the
  type and the name, so `(name, type)` pairs map to unique ids.
- **C**: chunks, each with an id, a document id and character offsets.
- **V**: edges `(s, r, o)` with `s, o` in E and `r` in R.
- **P**: a provenance map from each edge to a non-empty set of chunk ids in C.

## 2. Well-formedness constraints

An edge `(s, r, o)` can be stored only if:

1. **Typing.** `type(s)` is in `dom(r)` and `type(o)` is in `ran(r)`.
2. **Provenance.** `P(s, r, o)` is non-empty and every id in it names a stored chunk.
3. **Endpoints exist.** Both `s` and `o` are already in E.
4. **No self-loops from resolution.** The build step drops an edge whose endpoints resolve to the
   same entity.

Ontology consistency (checked when the ontology is loaded):

- Relation names are `UPPER_SNAKE_CASE`.
- Every type in a domain or range is declared in T.
- If `symmetric(r)`, then `dom(r) = ran(r)`.
- If `inverse(r) = r'`, then `r'` exists, `dom(r') = ran(r)` and `ran(r') = dom(r)`.

## 3. Materialised rules

Storing an edge also stores its logical consequences, so traversal needs only outgoing edges:

| Rule | If stored | Also stored |
| --- | --- | --- |
| Symmetry | `(a, r, b)` and `symmetric(r)` | `(b, r, a)` |
| Inverse | `(a, r, b)` and `inverse(r) = r'` | `(b, r', a)` |

Both new edges carry the same provenance as the original. These are the only inference rules.
Transitivity (for example `LOCATED_IN`) is **not** assumed; it is obtained by following a
multi-hop path, which keeps every step citable.

## 4. Paths and answers

A **path** of length *k* is a sequence of edges `(e1, ..., ek)` where the target of `ei` is the
source of `e(i+1)`.

- Paths are **cycle-free**: no entity occurs twice, including the start.
- A query fixes a **hop bound** `h` (default 3), so `1 <= k <= h`.
- A **supported answer** is the end entity of a path, and the answer text lists every edge on the
  path with the chunk ids from P.
- If no path exists within `h` hops the system **abstains**; it never fills the gap.

Formally, with `R_q` the relations suggested by cue words in the question (or all of R if there
are none), a one-entity question about `a` returns `{ end(p) : p is a path from a, k <= h,
every edge relation in R_q }`. A question linking entities `a` and `b` returns all paths from
`a` to `b` with `k <= h`, ignoring `R_q`.

## 5. Entity resolution

Mentions with the same type are clustered. Two names fall in one cluster when their normalised
forms are equal, or when their similarity ratio is at least `0.92`. Pairs with a ratio in
`[0.80, 0.92)` are listed as *possible duplicates* and are **not** merged. Names of different
types are never compared. Normalisation lower-cases, removes punctuation, collapses whitespace
and drops trailing company suffixes (Inc, Ltd, LLC, ...).

## 6. What the model does not capture

- Time: facts have no validity interval and cannot be superseded.
- Negation, modality and uncertainty beyond a stored confidence number.
- n-ary relations and relation attributes. Everything is a binary edge.
- Conflicting facts: two sources that disagree both produce edges.
- Open-world inference. Absence of an edge means "not found in the indexed text", not "false".

## 7. Example

Ontology fragment: `WORKS_AT: Person -> Organization`, `HEADQUARTERED_IN: Organization -> Location`,
`LOCATED_IN: Location -> Location`.

From the fictional sample text:

```text
Mira Okafor works at Helio Systems.        -> (Mira Okafor, WORKS_AT, Helio Systems)
Helio Systems is headquartered in Lisbon.  -> (Helio Systems, HEADQUARTERED_IN, Lisbon)
Lisbon is located in Portugal.             -> (Lisbon, LOCATED_IN, Portugal)
```

The question "How is Mira Okafor connected to Portugal?" links two entities and returns the single
3-hop path through those edges, each cited to the sentence it came from.
