import math

import duckdb
import polars as pl
import pytest

from dvi.profiling import profile_column
from dvi.warehouse import DuckDBDialect, SqlProfileSource

_PL_TO_DUCKDB = {
    pl.Utf8: "VARCHAR",
    pl.Float64: "DOUBLE",
    pl.Float32: "DOUBLE",
    pl.Int64: "BIGINT",
    pl.Int32: "BIGINT",
    pl.Boolean: "BOOLEAN",
}


def _load(con, table, df: pl.DataFrame) -> None:
    """Materialize a Polars frame into a DuckDB table via plain-Python inserts.

    DuckDB's register()/Arrow path needs pyarrow, which is unavailable, so we
    CREATE TABLE with mapped types and executemany the rows.
    """
    cols = ", ".join(f'"{name}" {_PL_TO_DUCKDB[dt]}' for name, dt in df.schema.items())
    con.execute(f'CREATE TABLE "{table}" ({cols})')
    placeholders = ", ".join("?" for _ in df.columns)
    rows = [tuple(r) for r in df.iter_rows()]
    if rows:
        con.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)


def _source(con, table, **kw) -> SqlProfileSource:
    return SqlProfileSource(
        lambda sql: con.execute(sql).fetchall(),
        table,
        dialect=DuckDBDialect(),
        **kw,
    )


def test_categorical_profile_matches_profile_column():
    df = pl.DataFrame({"country": ["UK", "US", "US", "DE", None, "US"]})
    con = duckdb.connect()
    _load(con, "t", df)

    got = _source(con, "t").profile(["country"])["country"]
    want = profile_column(df["country"])

    assert got.row_count == want.row_count == 6
    assert got.null_count == want.null_count == 1
    assert got.distinct_count == want.distinct_count == 3
    assert got.top_k == want.top_k
    assert got.numeric is None and want.numeric is None


def test_numeric_profile_matches_profile_column_within_epsilon():
    values = [float(v) for v in range(1, 101)]
    df = pl.DataFrame({"amount": values})
    con = duckdb.connect()
    _load(con, "t", df)

    got = _source(con, "t").profile(["amount"])["amount"]
    want = profile_column(df["amount"])

    assert got.numeric is not None
    assert got.numeric.count == want.numeric.count == 100
    assert math.isclose(got.numeric.mean, want.numeric.mean, rel_tol=1e-9)
    assert math.isclose(got.numeric.stddev, want.numeric.stddev, rel_tol=1e-9)
    assert math.isclose(got.numeric.minimum, want.numeric.minimum)
    assert math.isclose(got.numeric.maximum, want.numeric.maximum)
    for name in ("p05", "p25", "p50", "p75", "p95"):
        assert math.isclose(
            got.numeric.quantiles[name], want.numeric.quantiles[name], rel_tol=1e-9
        )


def test_profile_all_columns_when_none_requested():
    df = pl.DataFrame({"country": ["UK", "US"], "amount": [1.0, 2.0]})
    con = duckdb.connect()
    _load(con, "t", df)

    profiles = _source(con, "t").profile()

    assert set(profiles) == {"country", "amount"}


def test_single_row_numeric_has_zero_stddev():
    df = pl.DataFrame({"amount": [5.0]})
    con = duckdb.connect()
    _load(con, "t", df)

    got = _source(con, "t").profile(["amount"])["amount"]

    assert got.numeric is not None
    assert got.numeric.count == 1
    assert got.numeric.stddev == 0.0


def test_all_null_numeric_column_has_no_numeric_stats():
    df = pl.DataFrame({"amount": pl.Series([None, None, None], dtype=pl.Float64)})
    con = duckdb.connect()
    _load(con, "t", df)

    got = _source(con, "t").profile(["amount"])["amount"]

    assert got.row_count == 3
    assert got.null_count == 3
    assert got.distinct_count == 0
    assert got.top_k == {}
    assert got.numeric is None


def test_qualified_table_name_resolves_on_duckdb():
    # A schema-qualified table must be quoted per-part ("main"."t") and still
    # resolve against real DuckDB — quoting the whole dotted string would break it.
    df = pl.DataFrame({"country": ["UK", "US", "US"]})
    con = duckdb.connect()
    _load(con, "t", df)

    got = _source(con, "main.t").profile(["country"])["country"]

    assert got.row_count == 3
    assert got.distinct_count == 2


def test_unknown_column_raises_valueerror():
    df = pl.DataFrame({"country": ["UK"]})
    con = duckdb.connect()
    _load(con, "t", df)

    with pytest.raises(ValueError, match="ghost"):
        _source(con, "t").profile(["ghost"])


def test_misshaped_aggregate_row_raises_valueerror():
    df = pl.DataFrame({"country": ["UK"]})
    con = duckdb.connect()
    _load(con, "t", df)

    real = SqlProfileSource(
        lambda sql: con.execute(sql).fetchall(), "t", dialect=DuckDBDialect()
    )

    def bad_execute(sql):
        rows = con.execute(sql).fetchall()
        if "row_count" in sql:  # truncate the aggregate row
            return [row[:1] for row in rows]
        return rows

    broken = SqlProfileSource(bad_execute, "t", dialect=DuckDBDialect())
    with pytest.raises(ValueError, match="aggregate"):
        broken.profile(["country"])
    # sanity: the real source succeeds on the same table
    assert real.profile(["country"])["country"].row_count == 1
