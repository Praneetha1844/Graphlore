# Command-line reference

```text
graphlore [--ontology PATH] <command> [options]
```

`--ontology` (default `ontology/default.yaml`, or `$GRAPHLORE_ONTOLOGY`) is read by every
command. Errors are printed as `error: ...` on stderr and the exit status is `1`.

## build

Read documents, chunk them, extract triples, validate them against the ontology, resolve entity
names and write a graph as JSON.

```bash
graphlore build --input examples/corpus --output graph.json
graphlore build --input notes/ --ontology my.yaml --gazetteer my-entities.yaml
graphlore build --input notes/ --extractor llm --provider ollama --model <model-name>
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--input` | required | A `.txt`, `.md` or `.pdf` file, or a folder searched recursively. PDF needs the `pdf` extra. |
| `--output` | `graph.json` | Where to write the graph. |
| `--extractor` | `rules` | `rules` (gazetteer plus trigger phrases), `spacy` (needs the `spacy` extra and a model) or `llm`. |
| `--gazetteer` | `ontology/gazetteer.yaml` (or `$GRAPHLORE_GAZETTEER`) | Entity list for the `rules` extractor. |
| `--max-chars` | 500 | Maximum chunk size in characters (at least 50). |
| `--overlap` | 1 | Sentences repeated between consecutive chunks. |
| `--provider`, `--model`, `--allow-remote` | `ollama`, none, off | Model options for `--extractor llm`. `openai` sends document text to a remote service and needs `--allow-remote`. |

Document ids are the relative path without the suffix, so two files such as `notes.md` and
`notes.txt` in one folder are rejected. The command prints counts, any possible duplicate
entity names that were *not* merged, and the output path. With the `rules` extractor, gazetteer
aliases are stored on the entities so questions can use them.

## query

```bash
graphlore query "Where does Mira Okafor work?"
graphlore query "How is Mira Okafor connected to Portugal?" --max-hops 4
graphlore query "Who founded Northwind Labs?" --phrase --model <model-name>
```

| Option | Default | Meaning |
| --- | --- | --- |
| `question` | required | The question. It must mention entity names or aliases that are in the graph. |
| `--graph` | `graph.json` | Graph written by `build`. It is re-validated on load. |
| `--max-hops` | 3 | Longest path to follow (at least 1). |
| `--max-paths` | 10 | Most paths to return (at least 1). |
| `--phrase` | off | Ask a model to rewrite the evidence as a sentence. Falls back to the plain evidence if the model fails or names none of the answer entities. Needs `--model`. |

The answer lists each path with numbered citations and a **Sources** section quoting the
supporting chunks. If nothing in the graph supports an answer, the output says so instead of
guessing.

## export

```bash
graphlore export --format graphml --output graph.graphml
graphlore export --format json --output copy.json
```

GraphML cannot store lists, so aliases and chunk ids are joined with `;`.

## eval

```bash
graphlore eval --qa eval/qa.jsonl
```

Prints a JSON object with `items`, `abstained`, `exact_match` and `mean_path_recall`. The
question file is JSON lines: `{"question": "...", "answers": ["..."], "gold_edges": [["subject",
"PREDICATE", "object"]]}`. Both `answers` and `gold_edges` are optional per line. The bundled
file is a tiny hand-written sample; no results are shipped with the repository.
