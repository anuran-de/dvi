"""Compute a :class:`ColumnProfile` from column data.

The M1 path profiles an in-memory Polars ``Series``. A warehouse pushdown path
(computing the same profile via SQL, extracting only the compact result) is on
the roadmap (M5) and will produce the same ``ColumnProfile`` shape.
"""

from __future__ import annotations

import polars as pl

from .profile import ColumnProfile

DEFAULT_TOP_K = 50


def profile_column(series: pl.Series, top_k: int = DEFAULT_TOP_K) -> ColumnProfile:
    """Profile a single column into a :class:`ColumnProfile`.

    ``top_k`` bounds how many of the most frequent values are retained; this
    keeps the profile compact for high-cardinality columns while preserving the
    dominant categories that semantic detection reasons about.
    """
    row_count = series.len()
    null_count = int(series.null_count())

    non_null = series.drop_nulls()
    distinct_count = int(non_null.n_unique())

    counts: dict[str, int] = {}
    if non_null.len() > 0:
        vc = non_null.value_counts(sort=True)
        value_col, count_col = vc.columns[0], vc.columns[1]
        for value, count in zip(
            vc[value_col].to_list(), vc[count_col].to_list(), strict=True
        ):
            if len(counts) >= top_k:
                break
            counts[str(value)] = int(count)

    return ColumnProfile(
        name=series.name or "",
        row_count=row_count,
        null_count=null_count,
        distinct_count=distinct_count,
        top_k=counts,
    )
