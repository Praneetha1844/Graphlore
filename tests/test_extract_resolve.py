import json

import pytest
from conftest import GAZETTEER_PATH

from graphlore.extract import Gazetteer, LLMExtractor, RuleExtractor, load_gazetteer
from graphlore.llm import FakeProvider
from graphlore.models import Chunk
from graphlore.resolver import normalise, resolve_entities


@pytest.fixture
def gazetteer(ontology) -> Gazetteer:
    return load_gazetteer(GAZETTEER_PATH, ontology)


def chunk(text: str) -> Chunk:
    return Chunk("c:0", "c", text, 0, len(text))


def test_gazetteer_prefers_the_longest_match_and_is_case_insensitive(gazetteer) -> None:
    mentions = gazetteer.find("helio systems and Helio met MIRA OKAFOR")
    assert [(m.name, m.type) for m in mentions] == [
        ("Helio Systems", "Organization"),
        ("Helio Systems", "Organization"),
        ("Mira Okafor", "Person"),
    ]


def test_gazetteer_respects_word_boundaries(gazetteer) -> None:
    assert gazetteer.find("Rusty tools and Rustic charm") == []


def test_gazetteer_rejects_bad_entries(ontology) -> None:
    with pytest.raises(ValueError):
        Gazetteer([{"name": "X", "type": "Spaceship"}], ontology)
    with pytest.raises(ValueError):
        Gazetteer(
            [
                {"name": "Alpha", "type": "Person", "aliases": ["Al"]},
                {"name": "Alan", "type": "Person", "aliases": ["Al"]},
            ],
            ontology,
        )


def test_rule_extractor_pairs_adjacent_mentions_with_triggers(ontology, gazetteer) -> None:
    text = "Mira Okafor works at Helio Systems. Lisbon is located in Portugal."
    triples = RuleExtractor(ontology, gazetteer).extract(chunk(text))
    assert [(t.subject, t.predicate, t.object) for t in triples] == [
        ("Mira Okafor", "WORKS_AT", "Helio Systems"),
        ("Lisbon", "LOCATED_IN", "Portugal"),
    ]
    assert {t.chunk_id for t in triples} == {"c:0"}


def test_rule_extractor_respects_types_and_triggers(ontology, gazetteer) -> None:
    extractor = RuleExtractor(ontology, gazetteer)
    assert extractor.extract(chunk("Helio Systems works at Mira Okafor.")) == []  # wrong types
    assert extractor.extract(chunk("Mira Okafor admires Helio Systems.")) == []  # no trigger
    assert extractor.extract(chunk("Mira Okafor and Tomas Reyes work at Helio Systems.")) == []


def triples_json(*items: dict) -> str:
    return json.dumps({"triples": list(items)})


GOOD = {
    "subject": "Mira Okafor", "subject_type": "Person", "predicate": "WORKS_AT",
    "object": "Helio Systems", "object_type": "Organization",
}


def test_llm_extractor_keeps_grounded_ontology_valid_triples(ontology) -> None:
    text = "Mira Okafor works at Helio Systems."
    fenced = "```json\n" + triples_json(GOOD) + "\n```"
    extractor = LLMExtractor(FakeProvider([fenced]), ontology)
    (triple,) = extractor.extract(chunk(text))
    assert (triple.subject, triple.predicate, triple.chunk_id) == ("Mira Okafor", "WORKS_AT", "c:0")
    assert extractor.rejected == 0


def test_llm_extractor_drops_ungrounded_and_invalid_triples(ontology) -> None:
    invented = GOOD | {"object": "Ghost Corp"}
    wrong_types = GOOD | {"predicate": "LOCATED_IN"}
    incomplete = {"subject": "Mira Okafor"}
    reply = triples_json(GOOD, invented, wrong_types, incomplete)
    extractor = LLMExtractor(FakeProvider([reply]), ontology)
    triples = extractor.extract(chunk("Mira Okafor works at Helio Systems."))
    assert len(triples) == 1 and extractor.rejected == 3


def test_llm_extractor_survives_bad_replies(ontology) -> None:
    extractor = LLMExtractor(FakeProvider(["not json", "[1, 2]"]), ontology)
    assert extractor.extract(chunk("Mira Okafor works at Helio Systems.")) == []
    assert extractor.extract(chunk("Mira Okafor works at Helio Systems.")) == []
    assert extractor.rejected == 2


# ---- entity resolution


def test_normalise_strips_punctuation_and_company_suffixes() -> None:
    assert normalise("Helio Systems, Inc.") == "helio systems"
    assert normalise("  Helio   Systems ") == "helio systems"
    assert normalise("Inc") == "inc"  # a lone token is never removed


def test_variants_merge_to_the_most_frequent_form() -> None:
    mentions = [("Helio Systems", "Organization")] * 3 + [("Helio Systems Inc.", "Organization")]
    result = resolve_entities(mentions)
    assert result.resolve("Organization", "Helio Systems Inc.") == "Helio Systems"
    assert result.resolve("Organization", "Helio Systems") == "Helio Systems"


def test_close_spelling_merges_but_the_review_band_does_not() -> None:
    org = "Organization"
    merged = resolve_entities([("Helio Systems", org), ("Helio Systemz", org)])
    assert len({merged.resolve("Organization", n) for n in ("Helio Systems", "Helio Systemz")}) == 1

    review = resolve_entities([("Helio Systems", org), ("Helio Syst", org)])
    assert review.resolve("Organization", "Helio Syst") == "Helio Syst"
    pairs = [(a, b) for _, a, b, _ in review.possible_duplicates]
    assert pairs == [("Helio Syst", "Helio Systems")]


def test_names_never_merge_across_types() -> None:
    result = resolve_entities([("Paris", "Person"), ("Paris", "Location")])
    assert result.resolve("Person", "Paris") == "Paris"
    assert result.resolve("Location", "Paris") == "Paris"
    assert result.possible_duplicates == []
