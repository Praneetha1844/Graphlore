# Glossary

| Term | Meaning in Graphlore |
| --- | --- |
| **Ontology** | The allowed entity types and typed relations, with trigger phrases and question cues. |
| **Entity** | A named thing with a type, for example `Helio Systems` of type `Organization`. Its id is derived from type and name. |
| **Alias** | Another surface form of an entity's name, used when linking a question to the graph. |
| **Gazetteer** | A hand-maintained list of known entities and aliases used by the rule-based extractor. |
| **Chunk** | A group of consecutive sentences with character offsets into its document. |
| **Triple** | One extracted statement: subject, predicate, object, and the chunk it came from. |
| **Edge** | A stored triple. It always cites at least one existing chunk. |
| **Provenance** | The link from an edge back to the chunk (and so the text) that supports it. |
| **Trigger** | A phrase between two mentions ("works at") that signals a relation in text. |
| **Cue** | A word in a question ("work") that hints which relation to follow. |
| **Inverse / symmetric relation** | A relation stored in both directions automatically, so traversal only follows outgoing edges. |
| **Entity resolution** | Merging variant spellings of the same name within one entity type. |
| **Hop** | One edge on a path. `--max-hops` bounds path length. |
| **Abstain** | Return "no supported answer" because no entity or no path supports one. |
| **Grounded** | A model-proposed name that literally appears, as a whole phrase, in the chunk. |
| **Exact match / path recall** | The two metrics in the evaluation harness: answer entities equal the expected set, and the share of gold edges found in returned paths. |
