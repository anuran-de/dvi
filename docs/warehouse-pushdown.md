# Warehouse pushdown profiling (M5a)

DVI's semantic detectors consume a compact `ColumnProfile`, never raw rows. The
pushdown path computes that profile **in the warehouse via SQL** and returns only
the profile — so profiling a billion-row table moves a handful of aggregates, not
the table.

## The executor contract

`SqlProfileSource` never opens a connection. You pass a thin callable:

```python
execute: Callable[[str], Iterable[Sequence]]  # DBAPI fetchall() shape
```

Your code owns the connection, auth, and lifecycle. DVI builds the SQL (via a
dialect) and adapts the returned rows into `ColumnProfile`.

## DuckDB (CI-executed reference)

```python
import duckdb
from dvi.warehouse import DuckDBDialect, SqlProfileSource

con = duckdb.connect("warehouse.duckdb")
source = SqlProfileSource(
    lambda sql: con.execute(sql).fetchall(),
    table="analytics.orders",
    dialect=DuckDBDialect(),
)
profiles = source.profile(["country", "amount"])  # dict[str, ColumnProfile]
```

Feed the before/after profile dicts to `analyze_change_from_profiles`:

```python
from dvi.pipeline import analyze_change_from_profiles

incident = analyze_change_from_profiles(
    asset="model.shop.fact_orders",
    before=before_profiles,
    after=after_profiles,
    observed_at=observed_at,
    lineage=lineage,
    changes=changes,
    columns=["country", "amount"],
)
```

## Snowflake

`SnowflakeDialect` emits Snowflake-flavored SQL (`DESCRIBE TABLE`,
`PERCENTILE_CONT ... WITHIN GROUP`, a non-finite exclusion predicate). Its SQL is
unit-tested by string assertion but **not executed in CI** — the Snowflake driver
pulls `pyarrow`, which DVI deliberately avoids. Wire a real cursor yourself:

```python
import snowflake.connector
from dvi.warehouse import SnowflakeDialect, SqlProfileSource

conn = snowflake.connector.connect(...)  # your account/creds
cur = conn.cursor()

def execute(sql):
    cur.execute(sql)
    return cur.fetchall()

source = SqlProfileSource(execute, table="ANALYTICS.ORDERS", dialect=SnowflakeDialect())
profiles = source.profile(["COUNTRY", "AMOUNT"])
```

## Detection-equivalence guarantee

The pushdown path is held to a **detection-equivalent** bar: on the same data it
must yield the same incidents as the local Polars path. `tests/test_pushdown_equivalence.py`
runs both engines on categorical (value-substitution) and numeric (unit-scale)
changes and asserts decision-identical incidents. Individual float fields may
differ in their last digits; the decision may not.
