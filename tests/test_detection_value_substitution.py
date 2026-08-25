from dvi.detection import Symptom, detect_value_substitution
from dvi.profiling import ColumnProfile


def _profile(name: str, top_k: dict[str, int], nulls: int = 0) -> ColumnProfile:
    row_count = sum(top_k.values()) + nulls
    return ColumnProfile(
        name=name,
        row_count=row_count,
        null_count=nulls,
        distinct_count=len(top_k),
        top_k=top_k,
    )


def test_detects_uk_to_united_kingdom_substitution():
    # Non-null counts sum to 1000, so shares read directly as fractions.
    baseline = _profile("country", {"US": 620, "UK": 200, "DE": 120, "FR": 60})
    current = _profile("country", {"US": 622, "United Kingdom": 198, "DE": 122, "FR": 58})

    symptom = detect_value_substitution(baseline, current)

    assert isinstance(symptom, Symptom)
    assert symptom.signature == "value_substitution"
    assert symptom.column == "country"
    assert symptom.from_value == "UK"
    assert symptom.to_value == "United Kingdom"
    # ~20% of the distribution relocated from "UK" to "United Kingdom"
    assert 0.18 <= symptom.magnitude <= 0.21


def test_no_symptom_when_distribution_unchanged():
    baseline = _profile("country", {"US": 380, "UK": 120, "DE": 84})
    current = _profile("country", {"US": 382, "UK": 118, "DE": 85})

    assert detect_value_substitution(baseline, current) is None


def test_no_symptom_on_pure_volume_drop_with_stable_shares():
    # Row count halves but proportions are identical -> not a substitution.
    baseline = _profile("country", {"US": 400, "UK": 100})
    current = _profile("country", {"US": 200, "UK": 50})

    assert detect_value_substitution(baseline, current) is None


def test_ignores_tiny_noise_values_below_threshold():
    # A negligible rare value flickering must not trigger a substitution.
    baseline = _profile("country", {"US": 500, "UK": 499, "ZZ": 1})
    current = _profile("country", {"US": 500, "UK": 499, "QQ": 1})

    assert detect_value_substitution(baseline, current) is None


def test_tie_break_is_deterministic():
    # Two equal-mass drops and two equal-mass gains: the chosen pair must be
    # stable across runs (independent of set/hash iteration order).
    baseline = _profile("country", {"AA": 250, "BB": 250, "US": 500})
    current = _profile("country", {"XX": 250, "YY": 250, "US": 500})

    symptom = detect_value_substitution(baseline, current)

    assert symptom is not None
    # Deterministic tie-break: lexicographically smallest drop, then smallest gain.
    assert symptom.from_value == "AA"
    assert symptom.to_value == "XX"


def test_skips_high_cardinality_truncated_column():
    # top_k covers only a small fraction of non-null rows (a long tail was
    # truncated), so a value falling out of top_k would look like a phantom drop.
    # Value substitution is not trustworthy here and must not fire.
    baseline = ColumnProfile(
        name="user_id",
        row_count=1000,
        null_count=0,
        distinct_count=900,
        top_k={"UK": 200},  # covers 20% of rows; the rest is an untracked tail
    )
    current = ColumnProfile(
        name="user_id",
        row_count=1000,
        null_count=0,
        distinct_count=900,
        top_k={"United Kingdom": 200},
    )

    assert detect_value_substitution(baseline, current) is None
