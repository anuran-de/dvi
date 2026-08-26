import polars as pl

from dvi.profiling import ColumnProfile, profile_column


def test_profiles_categorical_counts_nulls_and_distinct():
    series = pl.Series("country", ["UK", "UK", "US", "US", "US", None])

    profile = profile_column(series)

    assert isinstance(profile, ColumnProfile)
    assert profile.name == "country"
    assert profile.row_count == 6
    assert profile.null_count == 1
    assert profile.distinct_count == 2  # UK, US (null excluded)


def test_top_k_holds_value_frequencies_as_counts():
    series = pl.Series("country", ["UK", "UK", "UK", "US", "DE"])

    profile = profile_column(series)

    assert profile.top_k == {"UK": 3, "US": 1, "DE": 1}


def test_top_k_truncation_breaks_count_ties_deterministically():
    # Six values all tied at count 1, keeping only two. Which two survive must not
    # depend on input/hash order: break ties by value (ascending) so the retained
    # boundary set is stable and reproducible across runs and machines.
    series = pl.Series("x", ["d", "c", "f", "a", "e", "b"])

    profile = profile_column(series, top_k=2)

    assert set(profile.top_k) == {"a", "b"}


def test_value_share_is_fraction_of_non_null_rows():
    series = pl.Series("country", ["UK", "UK", "US", "US", None])

    profile = profile_column(series)

    # 2 of 4 non-null rows are UK
    assert profile.value_share("UK") == 0.5
    assert profile.value_share("MISSING") == 0.0
