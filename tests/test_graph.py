import copy

import networkx as nx
import pytest

from graphlore.export import load_json, write_graphml, write_json
from graphlore.graph import NetworkXStore, OntologyViolation, ProvenanceError, entity_id
from graphlore.models import Chunk


@pytest.fixture
def store(ontology) -> NetworkXStore:
    s = NetworkXStore(ontology)
    s.add_chunk(Chunk("d:0", "d", "Mira Okafor works at Helio Systems.", 0, 35))
    s.add_chunk(Chunk("d:1", "d", "Mira Okafor joined Helio Systems.", 36, 70))
    return s


def people_and_org(store):
    mira = store.add_entity("Mira Okafor", "Person")
    helio = store.add_entity("Helio Systems", "Organization")
    return mira, helio


def test_entity_ids_and_alias_merging(store) -> None:
    assert entity_id("Mira Okafor", "Person") == "person:mira-okafor"
    key = store.add_entity("Mira Okafor", "Person", ["Mira"])
    store.add_entity("Mira Okafor", "Person", ["Dr. Okafor", "Mira Okafor"])
    assert store.entity(key).aliases == ("Dr. Okafor", "Mira")
    assert store.entity("person:nobody") is None


def test_unknown_entity_type_is_rejected(store) -> None:
    with pytest.raises(OntologyViolation):
        store.add_entity("Zorg", "Spaceship")


def test_edges_must_cite_a_stored_chunk(store) -> None:
    mira, helio = people_and_org(store)
    for bad in ("", "missing:9"):
        with pytest.raises(ProvenanceError):
            store.add_edge(mira, "WORKS_AT", helio, bad)
    assert store.neighbors(mira) == []


def test_edges_must_satisfy_the_ontology(store) -> None:
    mira, helio = people_and_org(store)
    with pytest.raises(OntologyViolation):
        store.add_edge(helio, "WORKS_AT", mira, "d:0")  # reversed domain and range
    with pytest.raises(OntologyViolation):
        store.add_edge(mira, "WORKS_AT", "organization:ghost", "d:0")  # endpoint missing


def test_inverse_and_symmetric_relations_are_materialised(store) -> None:
    mira, helio = people_and_org(store)
    other = store.add_entity("Brightpath Analytics", "Organization")
    store.add_edge(mira, "WORKS_AT", helio, "d:0")
    store.add_edge(helio, "COLLABORATES_WITH", other, "d:0")
    assert [e.predicate for e in store.neighbors(helio, {"EMPLOYS"})] == ["EMPLOYS"]
    assert [e.target for e in store.neighbors(other, {"COLLABORATES_WITH"})] == [helio]


def test_repeated_edges_merge_provenance(store) -> None:
    mira, helio = people_and_org(store)
    store.add_edge(mira, "WORKS_AT", helio, "d:0", 0.6)
    store.add_edge(mira, "WORKS_AT", helio, "d:1", 0.9)
    store.add_edge(mira, "WORKS_AT", helio, "d:1", 0.2)
    (edge,) = store.neighbors(mira, {"WORKS_AT"})
    assert edge.chunk_ids == ("d:0", "d:1") and edge.confidence == 0.9


def test_neighbors_filter_by_relation(store) -> None:
    mira, helio = people_and_org(store)
    store.add_edge(mira, "WORKS_AT", helio, "d:0")
    assert {e.predicate for e in store.neighbors(helio)} == {"EMPLOYS"}
    assert store.neighbors(helio, {"USES"}) == []
    assert store.neighbors("person:nobody") == []


def test_json_round_trip_preserves_everything(built, ontology, tmp_path) -> None:
    store, _ = built
    write_json(store, tmp_path / "g.json")
    loaded = load_json(tmp_path / "g.json", ontology)
    assert loaded.to_dict() == store.to_dict()


def test_loading_revalidates_against_the_ontology(built, ontology) -> None:
    store, _ = built
    data = copy.deepcopy(store.to_dict())
    mira = next(e for e in data["edges"] if e["predicate"] == "WORKS_AT")
    mira["predicate"] = "LOCATED_IN"  # Person -> Organization is not a valid LOCATED_IN
    with pytest.raises(OntologyViolation):
        NetworkXStore.from_dict(ontology, data)

    data = copy.deepcopy(store.to_dict())
    data["edges"][0]["chunk_ids"] = ["no-such-chunk"]
    with pytest.raises(ProvenanceError):
        NetworkXStore.from_dict(ontology, data)


def test_graphml_export_flattens_lists(built, tmp_path) -> None:
    store, _ = built
    write_graphml(store, tmp_path / "g.graphml")
    graph = nx.read_graphml(tmp_path / "g.graphml")
    assert graph.number_of_nodes() == len(store.entities())
    attributes = next(iter(graph.nodes(data=True)))[1]
    assert {"name", "type"} <= set(attributes)  # empty alias lists are omitted by GraphML
