from dvi.detection import Symptom, detect_unit_scale_shift
from dvi.profiling import ColumnProfile, NumericStats


def _num(name: str, qs: dict[str, float]) -> ColumnProfile:
    return ColumnProfile(
        name=name,
        row_count=1000,
        null_count=0,
        distinct_count=1000,
        numeric=NumericStats(
            count=1000,
            mean=qs["p50"],
            stddev=(qs["p95"] - qs["p05"]) / 3.29,
            minimum=qs["p05"],
            maximum=qs["p95"],
            quantiles=qs,
        ),
    )


def test_detects_multiplicative_unit_change_dollars_to_cents():
    base_qs = {"p05": 5, "p25": 20, "p50": 50, "p75": 80, "p95": 120}
    current_qs = {k: v * 100 for k, v in base_qs.items()}  # dollars -> cents

    symptom = detect_unit_scale_shift(_num("amount", base_qs), _num("amount", current_qs))

    assert isinstance(symptom, Symptom)
    assert symptom.signature == "unit_scale_shift"
    assert symptom.evidence["kind"] == "multiplicative"
    assert abs(symptom.evidence["factor"] - 100.0) < 1e-6
    assert symptom.magnitude == 1.0


def test_detects_additive_offset():
    base_qs = {"p05": 0, "p25": 6, "p50": 12, "p75": 18, "p95": 23}
    current_qs = {k: v + 5 for k, v in base_qs.items()}  # e.g. timezone offset

    symptom = detect_unit_scale_shift(_num("hour", base_qs), _num("hour", current_qs))

    assert symptom is not None
    assert symptom.evidence["kind"] == "additive"
    assert abs(symptom.evidence["offset"] - 5.0) < 1e-6


def test_shape_change_is_not_a_unit_shift():
    # Fans out around a stable median: not a rigid affine transform.
    baseline = _num("amount", {"p05": 45, "p25": 48, "p50": 50, "p75": 52, "p95": 55})
    current = _num("amount", {"p05": 20, "p25": 40, "p50": 50, "p75": 60, "p95": 80})

    assert detect_unit_scale_shift(baseline, current) is None


def test_stable_distribution_is_not_a_unit_shift():
    qs = {"p05": 5, "p25": 20, "p50": 50, "p75": 80, "p95": 120}
    assert detect_unit_scale_shift(_num("amount", qs), _num("amount", dict(qs))) is None


def test_returns_none_for_non_numeric():
    cat = ColumnProfile(
        name="country", row_count=10, null_count=0, distinct_count=2, top_k={"UK": 6, "US": 4}
    )
    assert detect_unit_scale_shift(cat, cat) is None
