from policy_layer2.config import Config
from policy_layer2.scope import Scope, ScopeLattice, compare_scopes


def _lattice():
    return ScopeLattice(Config())


def test_null_scope_is_universal_and_superset_of_scoped():
    lat = _lattice()
    a = Scope(role="all employees", system=None, geography=None)
    b = Scope(role=None, system="cloud", geography=None)
    result = compare_scopes(lat, a, b)
    # role: a=all employees, b=null(universal) -> b SUPERSET a on role
    assert result.role == "SUBSET"
    # system: a=null(universal), b=cloud -> a SUPERSET b on system
    assert result.system == "SUPERSET"
    assert result.geography == "EQUAL"
    # mixed SUPERSET/SUBSET across dimensions -> combined OVERLAP
    assert result.combined == "OVERLAP"


def test_disjoint_geography_forces_overall_disjoint():
    lat = _lattice()
    a = Scope(role=None, system=None, geography="eu")
    b = Scope(role=None, system=None, geography="us")
    result = compare_scopes(lat, a, b)
    assert result.geography == "DISJOINT"
    assert result.combined == "DISJOINT"


def test_role_lattice_superset_subset():
    lat = _lattice()
    a = Scope(role="all employees", system=None, geography=None)
    b = Scope(role="developers", system=None, geography=None)
    result = compare_scopes(lat, a, b)
    assert result.role == "SUPERSET"


def test_service_accounts_incomparable_to_all_employees():
    lat = _lattice()
    a = Scope(role="all employees", system=None, geography=None)
    b = Scope(role="service accounts", system=None, geography=None)
    result = compare_scopes(lat, a, b)
    assert result.role == "DISJOINT"


def test_equal_scopes():
    lat = _lattice()
    a = Scope(role="developers", system="cloud", geography="eu")
    b = Scope(role="developers", system="cloud", geography="eu")
    result = compare_scopes(lat, a, b)
    assert result.combined == "EQUAL"
