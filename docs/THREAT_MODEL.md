# Threat model

A short, honest description of what Graphlore defends against and what it does not. It is a
design review, not a security audit.

## Assets

- The documents you ingest, and the chunk text stored inside every graph file.
- The integrity of the graph: facts that look sourced but are not.
- API keys and database credentials for the optional integrations.

## Trust boundaries

| Input | Trust | Handling |
| --- | --- | --- |
| Source documents | Untrusted content | Treated as data. Only the model-based extractor sends them anywhere, and only to a provider you choose. |
| Model output (extraction, phrasing) | Untrusted | Triples must match the ontology and appear in the chunk as whole phrases. Phrased answers are accompanied by the plain evidence. |
| Graph JSON files | Untrusted | Re-validated on load: ontology typing and chunk provenance for every edge. |
| Ontology and gazetteer YAML | Trusted configuration | Parsed with `yaml.safe_load` and validated for consistency. |
| Questions | Untrusted | Matched against stored names only; no text is executed or interpolated into queries. |

## Threats and mitigations

| Threat | Mitigation | Residual risk |
| --- | --- | --- |
| A document tries to steer the extraction model ("ignore the ontology") | Text is delimited and labelled as data; output is filtered by ontology and grounding | A real but misleading sentence still yields a real edge; injected text can change which relations a model proposes between real entities |
| An invented fact enters the graph | Every edge must cite an existing chunk; model triples must be grounded in the text | Grounding checks that names appear, not that the relation is true |
| A tampered graph file asserts unsourced or ill-typed facts | Load re-validates every edge, or raises | A file can still cite real chunks for a wrong claim; the chunk text is inside the same file |
| Cypher injection through relation names | Predicates must be in the ontology and match `^[A-Z][A-Z_]*$` before entering a query; all values are bound parameters | The Neo4j adapter has not been tested against a live database |
| Document text leaves the machine | The default provider is local; `openai` is refused without `--allow-remote` | After consent, text goes to the configured endpoint |
| API key sent in clear text | Refused over plain `http` unless the host is `localhost` | Keys can still leak through shell history or CI logs |
| Runaway search on a dense graph | Hop limit, path limit and an expansion budget | Results may be truncated when the budget is reached |
| Sensitive text in graph files | None beyond keeping files private | Graph files contain full chunk text and should be treated like the source documents |

## Out of scope

- Authentication and authorisation of the Neo4j database or of the files on disk.
- Judging whether a source document is accurate. Conflicting sources both produce edges.
- Safe handling of malicious PDFs beyond what the `pypdf` library provides.

## Reporting a problem

See [SECURITY.md](../SECURITY.md).
