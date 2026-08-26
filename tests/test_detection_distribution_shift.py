from dvi.detection import Symptom, detect_numeric_distribution_shift
from dvi.profiling import ColumnProfile, NumericStats


def _num(name: str, qs: dict[str, float], mean: float, stddev: float) -> ColumnProfile:
    return ColumnProfile(
        name=name,
        row_count=1000,
        null_count=0,
        distinct_count=1000,
        numeric=NumericStats(
            count=1000,
            mean=mean,
            stddev=stddev,
            minimum=qs["p05"] - 10,
            maximum=qs["p95"] + 10,
            quantiles=qs,
        ),
    )


def test_detects_location_shift():
    baseline = _num("amount", {"p05": 30, "p25": 42, "p50": 50, "p75": 58, "p95": 70}, 50, 12)
    current = _num("amount", {"p05": 50, "p25": 62, "p50": 70, "p75": 78, "p95": 90}, 70, 12)

    symptom = detect_numeric_distribution_shift(baseline, current)

    assert isinstance(symptom, Symptom)
    assert symptom.signature == "numeric_distribution_shift"
    assert symptom.column == "amount"
    assert symptom.magnitude == 0.5  # 20-unit shift over a 40-unit baseline spread


def test_detects_spread_change_with_stable_median():
    baseline = _num("amount", {"p05": 45, "p25": 48, "p50": 50, "p75": 52, "p95": 55}, 50, 3)
    current = _num("amount", {"p05": 20, "p25": 40, "p50": 50, "p75": 60, "p95": 80}, 50, 20)

    symptom = detect_numeric_distribution_shift(baseline, current)

    assert symptom is not None
    assert symptom.magnitude > 0.5


def test_no_shift_when_distribution_stable():
    baseline = _num("amount", {"p05": 30, "p25": 42, "p50": 50, "p75": 58, "p95": 70}, 50, 12)
    current = _num("amount", {"p05": 31, "p25": 42, "p50": 50, "p75": 59, "p95": 70}, 50, 12)

    assert detect_numeric_distribution_shift(baseline, current) is None


def test_non_finite_quantile_does_not_fire():
    # Defense in depth: even if a non-finite quantile reaches the detector, the
    # guard `distance < threshold` must not fail open (nan < 0.1 is False) into a
    # bogus magnitude-1.0 symptom.
    baseline = _num("amount", {"p05": 30, "p25": 42, "p50": 50, "p75": 58, "p95": 70}, 50, 12)
    current = _num(
        "amount",
        {"p05": 30, "p25": 42, "p50": float("nan"), "p75": 58, "p95": 70},
        float("nan"),
        12,
    )

    assert detect_numeric_distribution_shift(baseline, current) is None


def test_returns_none_for_non_numeric_columns():
    baseline = ColumnProfile(
        name="country", row_count=10, null_count=0, distinct_count=2, top_k={"UK": 6, "US": 4}
    )
    current = ColumnProfile(
        name="country", row_count=10, null_count=0, distinct_count=2, top_k={"UK": 5, "US": 5}
    )

    assert detect_numeric_distribution_shift(baseline, current) is None
