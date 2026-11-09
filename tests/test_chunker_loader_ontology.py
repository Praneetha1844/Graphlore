import pytest

from graphlore.chunker import chunk_document, sentence_spans
from graphlore.loader import load_documents
from graphlore.models import Document
from graphlore.ontology import Ontology

SENTENCES = [f"Sentence number {n} stands alone." for n in range(1, 7)]
TEXT = " ".join(SENTENCES)


def test_sentence_spans_split_on_terminal_punctuation_and_capitals() -> None:
    text = "First one. Second one! Third? lowercase continues. Fourth"
    parts = [text[s:e] for s, e in sentence_spans(text)]
    assert parts == ["First one.", "Second one!", "Third? lowercase continues.", "Fourth"]


def test_chunks_respect_the_size_limit_and_keep_offsets() -> None:
    document = Document("doc", TEXT)
    chunks = chunk_document(document, max_chars=70, overlap=1)
    assert len(chunks) > 1
    assert [c.id for c in chunks] == [f"doc:{i}" for i in range(len(chunks))]
    for chunk in chunks:
        assert len(chunk.text) <= 70
        assert document.text[chunk.start : chunk.end] == chunk.text


def test_every_sentence_is_covered_and_overlap_repeats_one() -> None:
    chunks = chunk_document(Document("doc", TEXT), max_chars=70, overlap=1)
    covered = " ".join(c.text for c in chunks)
    assert all(s in covered for s in SENTENCES)
    for before, after in zip(chunks, chunks[1:], strict=False):
        last = before.text[sentence_spans(before.text)[-1][0] :]
        assert after.text.startswith(last)


def test_zero_overlap_shares_no_sentences() -> None:
    chunks = chunk_document(Document("doc", TEXT), max_chars=70, overlap=0)
    seen = [s for c in chunks for s in (c.text[a:b] for a, b in sentence_spans(c.text))]
    assert sorted(seen) == sorted(SENTENCES)


def test_overlong_sentence_becomes_its_own_chunk() -> None:
    long_sentence = "Word " * 40 + "end."
    chunks = chunk_document(Document("d", f"Short one. {long_sentence} Short two."), max_chars=60)
    assert any(len(c.text) > 60 for c in chunks)
    assert chunks[-1].text.endswith("Short two.")


def test_empty_text_and_invalid_arguments() -> None:
    assert chunk_document(Document("d", "   ")) == []
    with pytest.raises(ValueError):
        chunk_document(Document("d", TEXT), max_chars=10)
    with pytest.raises(ValueError):
        chunk_document(Document("d", TEXT), overlap=-1)


def test_loader_reads_nested_files_and_skips_empty_ones(tmp_path) -> None:
    (tmp_path / "a.md").write_text("Alpha text.", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("Beta text.", encoding="utf-8")
    (tmp_path / "blank.txt").write_text("  \n", encoding="utf-8")
    (tmp_path / "ignored.csv").write_text("x", encoding="utf-8")
    assert [d.id for d in load_documents(tmp_path)] == ["a", "sub/b"]


def test_loader_errors(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_documents(tmp_path / "missing")
    with pytest.raises(ValueError):
        load_documents(tmp_path)
    (tmp_path / "blank.txt").write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        load_documents(tmp_path)


# ---- ontology


def test_ontology_allows_only_declared_domain_and_range(ontology) -> None:
    assert ontology.allows("WORKS_AT", "Person", "Organization")
    assert not ontology.allows("WORKS_AT", "Organization", "Person")
    assert not ontology.allows("NOT_A_RELATION", "Person", "Organization")


def test_trigger_matching_uses_whole_words_and_types(ontology) -> None:
    assert ontology.match_trigger(" founded ", "Person", "Organization") == "FOUNDED"
    assert ontology.match_trigger(" profounded ", "Person", "Organization") is None
    assert ontology.match_trigger(" founded ", "Organization", "Person") is None
    assert ontology.match_trigger(" Works   at ", "Person", "Organization") is None  # spacing
    assert ontology.match_trigger(" WORKS AT ", "Person", "Organization") == "WORKS_AT"


def test_question_cues_suggest_relations(ontology) -> None:
    assert ontology.predicates_for_question("Where does Mira work?") == {"WORKS_AT"}
    assert ontology.predicates_for_question("Which company acquired Helio?") == {
        "ACQUIRED",
        "ACQUIRED_BY",
    }
    assert ontology.predicates_for_question("Tell me something") == set()


def _spec(**overrides):
    base = {"domain": ["A"], "range": ["B"]}
    return base | overrides


@pytest.mark.parametrize(
    "data",
    [
        {"entity_types": ["A", "B"], "relations": {"lower_case": _spec()}},
        {"entity_types": ["A"], "relations": {"REL": _spec()}},  # B undeclared
        {"entity_types": ["A", "B"], "relations": {"REL": _spec(symmetric=True)}},
        {"entity_types": ["A", "B"], "relations": {"REL": _spec(inverse="MISSING")}},
        {
            "entity_types": ["A", "B"],
            "relations": {"REL": _spec(inverse="BACK"), "BACK": _spec()},  # does not swap
        },
    ],
)
def test_inconsistent_ontologies_are_rejected(data) -> None:
    with pytest.raises(ValueError):
        Ontology.model_validate(data)
