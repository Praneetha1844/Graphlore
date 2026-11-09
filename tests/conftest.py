from pathlib import Path

import pytest

from graphlore.build import build_graph
from graphlore.extract import RuleExtractor, load_gazetteer
from graphlore.graph import NetworkXStore
from graphlore.loader import load_documents
from graphlore.ontology import Ontology, load_ontology

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_PATH = ROOT / "ontology" / "default.yaml"
GAZETTEER_PATH = ROOT / "ontology" / "gazetteer.yaml"
CORPUS_PATH = ROOT / "examples" / "corpus"
QA_PATH = ROOT / "eval" / "qa.jsonl"


@pytest.fixture
def ontology() -> Ontology:
    return load_ontology(ONTOLOGY_PATH)


@pytest.fixture
def built(ontology):
    """A store built from the hand-written fictional corpus, plus the build statistics."""
    store = NetworkXStore(ontology)
    extractor = RuleExtractor(ontology, load_gazetteer(GAZETTEER_PATH, ontology))
    stats = build_graph(load_documents(CORPUS_PATH), extractor, store, ontology)
    return store, stats
