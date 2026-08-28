"""Headline proof: the warehouse pushdown path yields the SAME incidents as the
local Polars path on the same data — categorical and numeric signatures alike."""

from datetime import datetime

import duckdb
import polars as pl

from dvi.benchmark import inject_value_substitution, make_orders
from dvi.lineage import LineageGraph
from dvi.pipeline import analyze_change, analyze_change_from_profiles
from dvi.rca import ChangeEvent
from dvi.warehouse import DuckDBDialect, SqlProfileSource

ASSET = "model.shop.fact_orders"

_PL_TO_DUCKDB = {pl.Utf8: "VARCHAR", pl.Float64: "DOUBLE", pl.Int64: "BIGINT"}


def _load(con, table, df: pl.DataFrame) -> None:
    cols = ", ".join(f'"{n}" {_PL_TO_DUCKDB[dt]}' for n, dt in df.schema.items())
    con.execute(f'CREATE TABLE "{table}" ({cols})')
    ph = ", ".join("?" for _ in df.columns)
    con.executemany(f'INSERT INTO "{table}" VALUES ({ph})', [tuple(r) for r in df.iter_rows()])


def _lineage() -> LineageGraph:
    g = LineageGraph()
    g.add_edge(ASSET, "model.shop.revenue_daily")
    g.add_edge("model.shop.revenue_daily", "model.shop.exec_dashboard")
    return g


def _pushdown_profiles(con, table, columns):
    src = SqlProfileSource(lambda sql: con.execute(sql).fetchall(), table, dialect=DuckDBDialect())
    return src.profile(columns)


def _assert_same_decision(polars_inc, pushdown_inc):
    # Non-vacuous: if a fixture ever stopped firing, both sides would silently
    # collapse to None and a naive `(a is None) == (b is None)` comparison would
    # pass on that vacuous agreement. Fail loudly instead.
    assert polars_inc is not None, "polars path produced no incident"
    assert pushdown_inc is not None, "pushdown path produced no incident"
    assert polars_inc.severity == pushdown_inc.severity
    ps = polars_inc.primary_cause.explained[0].symptom
    us = pushdown_inc.primary_cause.explained[0].symptom
    assert ps.signature == us.signature
    assert ps.column == us.column
    assert ps.from_value == us.from_value
    assert ps.to_value == us.to_value
    assert polars_inc.affected_assets == pushdown_inc.affected_assets
    # NOTE on numeric top_k: for numeric columns the profiler keys top_k with
    # Python `str(value)` while the SQL side uses `CAST(col AS VARCHAR)`; those
    # two representations can diverge for some floats (precision, scientific
    # notation). No numeric detector consults top_k for a decision, so this is
    # representational-only and intentionally NOT asserted here -- we compare
    # the decision (signature/column/from-to/severity/affected_assets), not the
    # raw profile payload.


def _run_both(before: pl.DataFrame, after: pl.DataFrame, columns):
    deploy = ChangeEvent("deploy-1", datetime(2026, 8, 25, 9, 0), [ASSET], "deploy")
    common = dict(
        asset=ASSET,
        observed_at=datetime(2026, 8, 25, 9, 5),
        lineage=_lineage(),
        changes=[deploy],
        columns=columns,
    )
    polars_inc = analyze_change(before=before, after=after, **common)

    con = duckdb.connect()
    _load(con, "before_t", before)
    _load(con, "after_t", after)
    pushdown_inc = analyze_change_from_profiles(
        before=_pushdown_profiles(con, "before_t", columns),
        after=_pushdown_profiles(con, "after_t", columns),
        **common,
    )
    return polars_inc, pushdown_inc


def test_value_substitution_decides_identically():
    before = make_orders(n=1000, uk_share=0.2, seed=7)
    after = inject_value_substitution(before, "country", "UK", "United Kingdom")
    _assert_same_decision(*_run_both(before, after, ["country"]))


def test_unit_scale_shift_decides_identically():
    before = make_orders(n=1000, uk_share=0.2, seed=7)
    # A silent unit change: amounts scaled x100 (e.g., dollars -> cents).
    after = before.with_columns((pl.col("amount") * 100.0).alias("amount"))
    _assert_same_decision(*_run_both(before, after, ["amount"]))


def test_case_format_normalization_decides_identically():
    before = make_orders(n=1000, uk_share=0.2, seed=7)
    # Every country code is re-cased ("UK" -> "uk"); same underlying categories
    # and masses, only the surface form moved.
    after = before.with_columns(pl.col("country").str.to_lowercase())
    _assert_same_decision(*_run_both(before, after, ["country"]))


def test_numeric_distribution_shift_decides_identically():
    before = make_orders(n=1000, uk_share=0.2, seed=7)
    # A genuine behavioral shift, not a unit/scale re-encoding: only the upper
    # tail fans out (values above 85 triple) while the lower quantiles hold
    # steady, so no single affine map (factor or offset) fits all of them --
    # unit_scale_shift must abstain and numeric_distribution_shift must fire.
    after = before.with_columns(
        pl.when(pl.col("amount") > 85.0)
        .then(pl.col("amount") * 3.0)
        .otherwise(pl.col("amount"))
        .alias("amount")
    )
    _assert_same_decision(*_run_both(before, after, ["amount"]))
