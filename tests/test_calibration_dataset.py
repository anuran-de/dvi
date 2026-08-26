"""The labelled calibration dataset: real positives, real+noise negatives."""

from dvi.benchmark.real_data import load_diamonds
from dvi.calibration.dataset import (
    GridPoint,
    LabeledSymptom,
    build_calibration_dataset,
    default_grid,
)

# A small, fast configuration reused across tests (the full default grid is
# exercised only by the frozen-model regression test).
_GRID = [
    GridPoint(column="clarity", from_value="SI1", to_value="SI1_X", n=2000, fraction=1.0),
    GridPoint(column="clarity", from_value="SI1", to_value="SI1_X", n=800, fraction=0.3),
    GridPoint(column="color", from_value="G", to_value="G_X", n=1500, fraction=0.5),
]
_NEG = dict(neg_columns=["cut", "color", "clarity", "price"], neg_sizes=[150, 300], neg_trials=6)


def _build(seed: int = 0) -> list[LabeledSymptom]:
    return build_calibration_dataset(seed=seed, df=load_diamonds(), grid=_GRID, **_NEG)


def test_default_grid_is_non_trivial():
    grid = default_grid()
    assert len(grid) >= 6
    assert all(isinstance(p, GridPoint) for p in grid)


def test_dataset_is_deterministic():
    a = _build()
    b = _build()
    assert [(s.features.as_list(), s.label, s.signature) for s in a] == [
        (s.features.as_list(), s.label, s.signature) for s in b
    ]


def test_dataset_contains_both_labels():
    rows = _build()
    labels = {s.label for s in rows}
    assert labels == {0, 1}


def test_positive_rate_is_in_a_sane_band():
    rows = _build()
    rate = sum(s.label for s in rows) / len(rows)
    assert 0.1 < rate < 0.95


def test_every_row_is_a_fired_symptom_with_finite_features():
    known = {
        "value_substitution",
        "category_split_merge",
        "case_format_normalization",
        "numeric_distribution_shift",
        "unit_scale_shift",
    }
    for s in _build():
        assert s.signature in known
        assert s.label in (0, 1)
        for v in s.features.as_list():
            assert v == v  # not NaN
