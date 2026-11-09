"""Command line interface: build, query, export, eval."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import yaml

from graphlore.build import build_graph
from graphlore.evaluate import evaluate, load_qa
from graphlore.export import load_json, write_graphml, write_json
from graphlore.extract import (
    Extractor,
    LLMExtractor,
    RuleExtractor,
    SpacyExtractor,
    load_gazetteer,
)
from graphlore.graph import NetworkXStore, OntologyViolation, ProvenanceError
from graphlore.llm import LLMError, LLMProvider, OllamaProvider, OpenAICompatProvider
from graphlore.loader import load_documents
from graphlore.ontology import Ontology, load_ontology
from graphlore.qa import answer_question, phrase_answer

# The container image sets these so the bundled sample files are found from any directory.
DEFAULT_ONTOLOGY = os.environ.get("GRAPHLORE_ONTOLOGY", "ontology/default.yaml")
DEFAULT_GAZETTEER = os.environ.get("GRAPHLORE_GAZETTEER", "ontology/gazetteer.yaml")


def build_provider(name: str, model: str, allow_remote: bool) -> LLMProvider:
    if name == "ollama":
        return OllamaProvider(model, os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    if not allow_remote:
        raise LLMError(
            "the openai provider sends document text to a remote service; "
            "pass --allow-remote to confirm"
        )
    return OpenAICompatProvider(
        model,
        os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        os.environ.get("OPENAI_API_KEY", ""),
    )


def _add_model_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", choices=["ollama", "openai"], default="ollama")
    parser.add_argument("--model")
    parser.add_argument("--allow-remote", action="store_true")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="graphlore", description=__doc__)
    parser.add_argument("--ontology", default=DEFAULT_ONTOLOGY)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="build a graph from documents")
    build.add_argument("--input", type=Path, required=True)
    build.add_argument("--output", type=Path, default=Path("graph.json"))
    build.add_argument("--extractor", choices=["rules", "spacy", "llm"], default="rules")
    build.add_argument("--gazetteer", default=DEFAULT_GAZETTEER)
    build.add_argument("--max-chars", type=int, default=500)
    build.add_argument("--overlap", type=int, default=1)
    _add_model_options(build)

    query = sub.add_parser("query", help="ask a question")
    query.add_argument("question")
    query.add_argument("--graph", type=Path, default=Path("graph.json"))
    query.add_argument("--max-hops", type=int, default=3)
    query.add_argument("--max-paths", type=int, default=10)
    query.add_argument("--phrase", action="store_true", help="rewrite the evidence with a model")
    _add_model_options(query)

    export = sub.add_parser("export", help="convert a graph")
    export.add_argument("--graph", type=Path, default=Path("graph.json"))
    export.add_argument("--format", choices=["graphml", "json"], required=True)
    export.add_argument("--output", type=Path, required=True)

    ev = sub.add_parser("eval", help="compute metrics on a question file")
    ev.add_argument("--graph", type=Path, default=Path("graph.json"))
    ev.add_argument("--qa", type=Path, required=True)
    ev.add_argument("--max-hops", type=int, default=3)
    return parser


def _extractor(args: argparse.Namespace, ontology: Ontology) -> Extractor:
    if args.extractor == "rules":
        return RuleExtractor(ontology, load_gazetteer(args.gazetteer, ontology))
    if args.extractor == "spacy":
        return SpacyExtractor(ontology)
    if not args.model:
        raise ValueError("--model is required for the llm extractor")
    return LLMExtractor(build_provider(args.provider, args.model, args.allow_remote), ontology)


def run(args: argparse.Namespace) -> int:
    ontology = load_ontology(args.ontology)

    if args.command == "build":
        store = NetworkXStore(ontology)
        extractor = _extractor(args, ontology)
        known = extractor.gazetteer.aliases() if isinstance(extractor, RuleExtractor) else None
        stats = build_graph(
            load_documents(args.input), extractor, store, ontology,
            args.max_chars, args.overlap, known,
        )
        write_json(store, args.output)
        print(
            f"{stats.documents} document(s), {stats.chunks} chunk(s), {stats.triples} triple(s) "
            f"kept, {stats.rejected} rejected, {stats.entities} entities, {stats.edges} edges"
        )
        for etype, a, b, score in stats.possible_duplicates:
            print(f"possible duplicate ({etype}): {a!r} ~ {b!r} ({score})")
        print(f"wrote {args.output}")
        return 0

    store = load_json(args.graph, ontology)

    if args.command == "query":
        answer = answer_question(store, ontology, args.question, args.max_hops, args.max_paths)
        if args.phrase:
            if not args.model:
                raise ValueError("--model is required with --phrase")
            provider = build_provider(args.provider, args.model, args.allow_remote)
            print(phrase_answer(answer, provider))
        else:
            print(answer.text)
        return 0

    if args.command == "export":
        if args.format == "graphml":
            write_graphml(store, args.output)
        else:
            write_json(store, args.output)
        print(f"wrote {args.output}")
        return 0

    summary = evaluate(load_qa(args.qa), store, ontology, args.max_hops)
    print(
        json.dumps(
            {
                "items": summary.items,
                "abstained": summary.abstained,
                "exact_match": summary.exact_match,
                "mean_path_recall": summary.mean_path_recall,
            },
            indent=2,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(_parser().parse_args(argv))
    except (
        OSError, ValueError, RuntimeError, KeyError, yaml.YAMLError, OntologyViolation,
        ProvenanceError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
