"""Synthetic data + failure injection for the DVI benchmark.

M1 ships the minimum needed to prove the hypothesis: an orders table with a
controllable ``country`` distribution, and a value-substitution injector. The
full multi-table benchmark with negatives, decoys and concurrent distractors
arrives in M2.
"""

from __future__ import annotations

import random

import polars as pl

_OTHER_COUNTRIES = ["US", "DE", "FR", "IN", "BR"]


def make_orders(n: int, uk_share: float = 0.2, seed: int = 0) -> pl.DataFrame:
    """Build a synthetic ``orders`` table with an exact ``UK`` share.

    ``UK`` gets exactly ``round(n * uk_share)`` rows; the remainder is spread
    deterministically across other countries. Row order is shuffled (seeded) for
    realism, but the category counts are exact so tests are deterministic.
    """
    uk_count = round(n * uk_share)
    countries = ["UK"] * uk_count
    for i in range(n - uk_count):
        countries.append(_OTHER_COUNTRIES[i % len(_OTHER_COUNTRIES)])

    rng = random.Random(seed)
    rng.shuffle(countries)

    return pl.DataFrame(
        {
            "order_id": list(range(1, n + 1)),
            "country": countries,
            "amount": [round(10 + (i % 90) + 0.99, 2) for i in range(n)],
        }
    )


def inject_value_substitution(
    df: pl.DataFrame, column: str, old: str, new: str
) -> pl.DataFrame:
    """Return a copy of ``df`` with every ``old`` in ``column`` relabelled ``new``.

    This is the silent rename: schema, row count and null rate are untouched.
    """
    return df.with_columns(
        pl.when(pl.col(column) == old)
        .then(pl.lit(new))
        .otherwise(pl.col(column))
        .alias(column)
    )
