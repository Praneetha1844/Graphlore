import json

import pytest
from conftest import CORPUS_PATH, GAZETTEER_PATH, ONTOLOGY_PATH, QA_PATH

from graphlore.cli import main
from graphlore.evaluate import evaluate, load_qa
from graphlore.llm import FakeProvider, LLMError
from graphlore.qa import answer_question, find_paths, link_entities, phrase_answer


class BrokenProvider:
    def complete(self, system: str, prompt: str) -> str:
        raise LLMError("offline")


# ---- build

def test_build_reports_what_it_did(built) -> None:
    store, stats = built
    assert stats.documents == 1 and stats.chunks >= 1
    assert stats.entities == 12 and stats.edges == 12 and stats.rejected == 0


def test_every_edge_traces_back_to_text_that_names_both_ends(built) -> None:
    store, _ = built
    for edge in store.edges():
        source, target = store.entity(edge.source), store.entity(edge.target)
        assert edge.chunk_ids
        for chunk_id in edge.chunk_ids:
            chunk = store.chunk(chunk_id)
            assert chunk is not None
            assert source.name in chunk.text and target.name in chunk.text


# ---- entity linking and retrieval

def test_linking_prefers_longest_names_and_orders_by_position(built) -> None:
    store, _ = built
    linked = link_entities(store, "is PORTUGAL linked to mira okafor, or to Helio Systems?")
    assert [e.name for e in linked] == ["Portugal", "Mira Okafor", "Helio Systems"]
    assert link_entities(store, "Nothing relevant here") == []


def test_paths_are_bounded_cycle_free_and_shortest_first(built) -> None:
    store, _ = built
    helio = "organization:helio-systems"
    paths = find_paths(store, helio, max_hops=3, max_paths=50)
    assert paths == sorted(paths, key=len)
    for path in paths:
        nodes = [helio] + [e.target for e in path]
        assert len(path) <= 3 and len(set(nodes)) == len(nodes)
    assert len(find_paths(store, helio, max_paths=2)) == 2
    with pytest.raises(ValueError):
        find_paths(store, helio, max_hops=0)


def test_expansion_budget_stops_the_search(built) -> None:
    store, _ = built
    assert find_paths(store, "organization:helio-systems", max_expansions=0) == []


# ---- answers

@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Where does Mira Okafor work?", ["Helio Systems"]),
        ("Who founded Northwind Labs?", ["Tomas Reyes"]),
        ("Where is Helio Systems headquartered?", ["Lisbon"]),
        ("Which company acquired Helio Systems?", ["Northwind Labs"]),
    ],
)
def test_single_entity_questions_follow_the_cued_relation(
    built, ontology, question, expected
) -> None:
    store, _ = built
    answer = answer_question(store, ontology, question)
    assert not answer.abstained and answer.answer_entities == expected


def test_connection_question_returns_the_supporting_path_with_citations(built, ontology) -> None:
    store, _ = built
    answer = answer_question(store, ontology, "How is Mira Okafor connected to Portugal?")
    (path,) = answer.paths
    assert [e.predicate for e in path] == ["WORKS_AT", "HEADQUARTERED_IN", "LOCATED_IN"]
    assert "Sources:" in answer.text and answer.citations[0].number == 1
    assert all(store.chunk(c.chunk_id) is not None for c in answer.citations)


def test_hop_limit_is_enforced(built, ontology) -> None:
    store, _ = built
    question = "How is Mira Okafor connected to Switzerland?"  # needs four hops
    assert answer_question(store, ontology, question, max_hops=3).abstained
    assert not answer_question(store, ontology, question, max_hops=4).abstained


def test_unknown_entities_and_missing_evidence_abstain(built, ontology) -> None:
    store, _ = built
    assert answer_question(store, ontology, "What is the weather?").abstained
    assert answer_question(store, ontology, "Who founded Lisbon?").abstained


def test_phrasing_is_optional_and_falls_back_to_the_evidence(built, ontology) -> None:
    store, _ = built
    answer = answer_question(store, ontology, "Where does Mira Okafor work?")
    good = phrase_answer(answer, FakeProvider(["Mira Okafor works at Helio Systems."]))
    assert good.startswith("Mira Okafor works at Helio Systems.") and answer.text in good
    assert phrase_answer(answer, FakeProvider(["I do not know."])) == answer.text
    assert phrase_answer(answer, BrokenProvider()) == answer.text


# ---- evaluation harness

def test_harness_computes_metrics_without_shipping_results(built, ontology) -> None:
    store, _ = built
    summary = evaluate(load_qa(QA_PATH), store, ontology)
    assert summary.items == 5 and summary.exact_match_items == 4
    assert summary.exact_match is not None and 0.0 <= summary.exact_match <= 1.0
    assert summary.mean_path_recall is not None


def test_qa_file_validation(tmp_path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"answers": []}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_qa(bad)
    bad.write_text('{"question": "q", "gold_edges": [["a", "b"]]}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_qa(bad)


# ---- command line

def test_cli_build_query_export_and_eval(tmp_path, capsys) -> None:
    ontology = ["--ontology", str(ONTOLOGY_PATH)]
    graph = tmp_path / "graph.json"
    assert main([*ontology, "build", "--input", str(CORPUS_PATH), "--output", str(graph),
                 "--gazetteer", str(GAZETTEER_PATH)]) == 0
    assert "12 entities" in capsys.readouterr().out

    assert main([*ontology, "query", "Where does Mira Okafor work?", "--graph", str(graph)]) == 0
    assert "Helio Systems" in capsys.readouterr().out

    target = tmp_path / "graph.graphml"
    assert main([*ontology, "export", "--graph", str(graph), "--format", "graphml",
                 "--output", str(target)]) == 0 and target.exists()
    capsys.readouterr()

    assert main([*ontology, "eval", "--graph", str(graph), "--qa", str(QA_PATH)]) == 0
    assert json.loads(capsys.readouterr().out)["items"] == 5


def test_cli_errors_exit_with_code_one(tmp_path, capsys) -> None:
    ontology = ["--ontology", str(ONTOLOGY_PATH)]
    assert main([*ontology, "query", "q", "--graph", str(tmp_path / "missing.json")]) == 1
    assert main([*ontology, "build", "--input", str(CORPUS_PATH), "--extractor", "llm"]) == 1
    remote = ["build", "--input", str(CORPUS_PATH), "--extractor", "llm",
              "--provider", "openai", "--model", "m"]
    assert main([*ontology, *remote]) == 1
    assert "--allow-remote" in capsys.readouterr().err
