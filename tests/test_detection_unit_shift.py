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


def test_near_identical_offset_distribution_is_not_a_unit_shift():
    # A real-data failure mode: a narrow-spread column living far from zero (e.g.
    # a percentage ~61) sampled twice. The two halves are the SAME distribution
    # (median 61.8 -> 61.9), but a joint slope+intercept fit turns quantile jitter
    # into a bogus "additive offset of +4". Fitting slope and offset separately,
    # each against sampling noise, must read this as no change.
    baseline = _num("depth", {"p05": 59.2, "p25": 61.0, "p50": 61.8, "p75": 62.5, "p95": 63.8})
    current = _num("depth", {"p05": 59.4, "p25": 61.1, "p50": 61.9, "p75": 62.5, "p95": 63.6})

    assert detect_unit_scale_shift(baseline, current) is None


def test_narrow_spread_far_from_zero_additive_drift_is_not_a_unit_shift():
    # A column pinned at ~61 with a spread of 0.04. A rigid +0.02 drift makes
    # abs(offset)/base_scale = 0.5 -> the additive test fires magnitude 0.5, but a
    # 0.02 move on values around 61 (0.03%) is jitter, not a unit re-encoding. The
    # near-constant column is effectively scale-free; #5 must not fire.
    base_qs = {"p05": 60.98, "p25": 60.99, "p50": 61.00, "p75": 61.01, "p95": 61.02}
    current_qs = {k: v + 0.02 for k, v in base_qs.items()}

    assert detect_unit_scale_shift(_num("depth", base_qs), _num("depth", current_qs)) is None


def test_returns_none_for_non_numeric():
    cat = ColumnProfile(
        name="country", row_count=10, null_count=0, distinct_count=2, top_k={"UK": 6, "US": 4}
    )
    assert detect_unit_scale_shift(cat, cat) is None
