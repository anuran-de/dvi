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
    assert (polars_inc is None) == (pushdown_inc is None)
    if polars_inc is None:
        return
    assert polars_inc.severity == pushdown_inc.severity
    ps = polars_inc.primary_cause.explained[0].symptom
    us = pushdown_inc.primary_cause.explained[0].symptom
    assert ps.signature == us.signature
    assert ps.column == us.column
    assert ps.from_value == us.from_value
    assert ps.to_value == us.to_value
    assert polars_inc.affected_assets == pushdown_inc.affected_assets


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
