import math

import polars as pl

from dvi.profiling import profile_column


def test_numeric_column_gets_numeric_stats():
    series = pl.Series("amount", [1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10])

    profile = profile_column(series)

    assert profile.numeric is not None
    assert profile.numeric.mean == 5.5
    assert profile.numeric.minimum == 1.0
    assert profile.numeric.maximum == 10.0
    assert profile.numeric.median == 5.5


def test_categorical_column_has_no_numeric_stats():
    series = pl.Series("country", ["UK", "US", "US"])

    profile = profile_column(series)

    assert profile.numeric is None


def test_numeric_stats_expose_ordered_quantiles():
    series = pl.Series("amount", list(range(1, 101)))  # 1..100

    profile = profile_column(series)

    q = profile.numeric.quantiles
    # Linear interpolation over 1..100: median sits at 50.5.
    assert q["p50"] == 50.5
    assert q["p05"] < q["p25"] < q["p50"] < q["p75"] < q["p95"]


def test_all_null_numeric_column_has_no_numeric_stats():
    series = pl.Series("amount", [None, None, None], dtype=pl.Float64)

    profile = profile_column(series)

    assert profile.numeric is None


def test_non_finite_values_are_excluded_from_numeric_stats():
    # A single NaN/inf must not poison the aggregates: polars mean/std/quantile
    # all return NaN when a NaN is present, and NaN sorts high so q95 becomes NaN.
    clean = [float(v) for v in range(1, 101)]  # 1.0..100.0
    series = pl.Series("amount", [*clean, float("nan"), float("inf"), float("-inf")])

    profile = profile_column(series)

    assert profile.numeric is not None
    q = profile.numeric.quantiles
    assert all(math.isfinite(v) for v in q.values())
    assert math.isfinite(profile.numeric.mean)
    assert math.isfinite(profile.numeric.stddev)
    # The finite subset is exactly 1..100, so its stats are unchanged.
    assert profile.numeric.mean == 50.5
    assert profile.numeric.maximum == 100.0


def test_all_non_finite_numeric_column_has_no_numeric_stats():
    series = pl.Series("amount", [float("nan"), float("inf"), float("-inf")])

    profile = profile_column(series)

    assert profile.numeric is None
