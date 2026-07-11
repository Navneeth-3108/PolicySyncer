from policy_layer2.config import Config
from policy_layer2.conflict import evaluate_conflict
from policy_layer2.nli import NLIEngine
from policy_layer2.normalize import build_deontic_proposition
from policy_layer2.scope import ScopeLattice


def _prop(**overrides):
    base = {
        "obligation_id": "X",
        "modal_normalized": "must",
        "polarity": "positive",
        "modal_strength": 3,
        "action": "encrypt",
        "object": "data",
        "qualifiers": [],
        "category_primary": "encryption",
        "category_secondary": [],
        "scope": {"role": None, "system": None, "geography": None},
        "temporal_constraint": None,
        "exception": {},
        "confidence": 0.8,
        "raw_text": "must encrypt data",
    }
    base.update(overrides)
    return build_deontic_proposition(base, policy_name="TestPolicy")


def test_obligation_vs_prohibition_same_scope_is_direct_conflict():
    config = Config()
    lattice = ScopeLattice(config)
    nli = NLIEngine(config)
    a = _prop(obligation_id="A", modal_normalized="must", polarity="positive")
    b = _prop(obligation_id="B", modal_normalized="must", polarity="negative")
    result = evaluate_conflict(a, b, action_similarity=0.9, lattice=lattice, nli_engine=nli)
    assert result is not None
    assert result.subtype == "DIRECT"


def test_disjoint_scope_suppresses_conflict_entirely():
    config = Config()
    lattice = ScopeLattice(config)
    nli = NLIEngine(config)
    a = _prop(obligation_id="A", modal_normalized="must", polarity="positive",
              scope={"role": None, "system": None, "geography": "eu"})
    b = _prop(obligation_id="B", modal_normalized="must", polarity="negative",
              scope={"role": None, "system": None, "geography": "us"})
    result = evaluate_conflict(a, b, action_similarity=0.9, lattice=lattice, nli_engine=nli)
    assert result is None


def test_exception_scope_override_suppresses_conflict():
    config = Config()
    lattice = ScopeLattice(config)
    nli = NLIEngine(config)
    a = _prop(
        obligation_id="A", modal_normalized="must", polarity="positive",
        scope={"role": "all employees", "system": None, "geography": None},
        exception={"scope_override": {"role": None, "system": "CI/CD", "geography": None}},
    )
    b = _prop(
        obligation_id="B", modal_normalized="may", polarity="positive",
        scope={"role": None, "system": "CI/CD", "geography": None},
    )
    result = evaluate_conflict(a, b, action_similarity=0.9, lattice=lattice, nli_engine=nli)
    assert result is None


def test_partial_overlap_when_scope_is_subset_superset():
    config = Config()
    lattice = ScopeLattice(config)
    nli = NLIEngine(config)
    a = _prop(obligation_id="A", modal_normalized="must", polarity="positive",
              scope={"role": "all employees", "system": None, "geography": None})
    b = _prop(obligation_id="B", modal_normalized="must", polarity="negative",
              scope={"role": "developers", "system": None, "geography": None})
    result = evaluate_conflict(a, b, action_similarity=0.9, lattice=lattice, nli_engine=nli)
    assert result is not None
    assert result.subtype == "PARTIAL_OVERLAP"
