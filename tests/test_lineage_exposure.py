from dvi.lineage import Criticality, Exposure, derive_criticality


def test_criticality_is_ordered_for_worst_of():
    assert Criticality.LOW < Criticality.MEDIUM < Criticality.HIGH < Criticality.CRITICAL
    assert max(Criticality.LOW, Criticality.HIGH) is Criticality.HIGH


def test_meta_override_wins_over_derivation():
    # An otherwise-medium dashboard flagged critical by its owner.
    c = derive_criticality("dashboard", "medium", {"criticality": "critical"})
    assert c is Criticality.CRITICAL


def test_customer_facing_application_at_high_maturity_is_critical():
    assert derive_criticality("application", "high", {}) is Criticality.CRITICAL


def test_application_below_high_maturity_is_high():
    assert derive_criticality("application", "medium", {}) is Criticality.HIGH


def test_ml_is_high():
    assert derive_criticality("ml", "low", {}) is Criticality.HIGH


def test_dashboard_maps_maturity():
    assert derive_criticality("dashboard", "high", {}) is Criticality.HIGH
    assert derive_criticality("dashboard", "medium", {}) is Criticality.MEDIUM
    assert derive_criticality("dashboard", "low", {}) is Criticality.LOW
    assert derive_criticality("dashboard", "", {}) is Criticality.MEDIUM  # default


def test_notebook_and_analysis_are_low():
    assert derive_criticality("notebook", "high", {}) is Criticality.LOW
    assert derive_criticality("analysis", "high", {}) is Criticality.LOW


def test_unknown_type_defaults_to_medium():
    assert derive_criticality("whatever", "high", {}) is Criticality.MEDIUM


def test_invalid_meta_override_falls_back_to_derivation():
    # A garbage override string must not crash; fall back to type/maturity.
    assert derive_criticality("ml", "low", {"criticality": "bogus"}) is Criticality.HIGH


def test_exposure_is_frozen_and_hashable():
    e = Exposure("exposure.shop.d", "d", "dashboard", Criticality.HIGH, "jane", "", frozenset({"m"}))
    assert e.criticality is Criticality.HIGH
    assert hash(e)  # frozen dataclass is hashable
