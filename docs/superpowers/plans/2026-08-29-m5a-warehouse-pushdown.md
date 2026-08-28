# M5a Warehouse Pushdown Profiling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute the same `ColumnProfile` in-warehouse via SQL (pulling back only the compact profile, not raw rows) and prove it yields the same incidents as the local Polars path.

**Architecture:** A new `src/dvi/warehouse/` package adds a *second producer* of `ColumnProfile`. `SqlDialect` (with `DuckDBDialect` and `SnowflakeDialect`) emits per-column profiling SQL; `SqlProfileSource` runs that SQL through a thin `execute(sql) -> rows` callable and adapts the result rows into `ColumnProfile`. `pipeline/analyze.py` gains a parallel `analyze_change_from_profiles` entry; the existing Polars `detect_symptoms` is refactored to delegate to a shared `detect_symptoms_from_profiles`, so both paths run identical detection logic.

**Tech Stack:** Python 3.11, DuckDB (CI-executed reference), Polars (existing local path), Pydantic v2 (`ColumnProfile`/`NumericStats`), pytest. Snowflake is SQL-generation only (no driver in CI — it pulls pyarrow, which is unavailable).

**Spec:** `docs/superpowers/specs/2026-08-27-m5a-warehouse-pushdown-design.md`

## Global Constraints

- **Python 3.11**; ruff line-length **100**; ruff lint select `E, F, I, UP, B`.
- **Available libs:** polars, duckdb, networkx, pydantic v2. **NOT available:** numpy, pandas, pyarrow, sklearn. Do not import them, directly or transitively (this is why the real Snowflake connector and DuckDB's `register()` Arrow path are off-limits).
- **The `ColumnProfile` produced by the SQL path must be field-for-field constructed the way `src/dvi/profiling/profiler.py` builds it** — same finite-value handling, same `stddev=0.0` at n=1, same `str(value)` top_k keys, same deterministic `(count desc, value asc)` ordering.
- **Commits:** author every commit as `Anuran De <121761842+anuran-de@users.noreply.github.com>` with **NO** `Co-Authored-By` trailer and **NO** "Generated with" line. Exact form:
  ```bash
  git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
    commit -m "<message>" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
  ```
- **Venv activation (Git Bash):** `source .venv/Scripts/activate` before running pytest.
- **Test-first:** every task follows RED → GREEN → commit. Run the full suite (`pytest -q`) before the final task's commit.

## File Structure

- `src/dvi/warehouse/__init__.py` — package exports: `SqlDialect`, `DuckDBDialect`, `SnowflakeDialect`, `SqlProfileSource`.
- `src/dvi/warehouse/dialect.py` — `SqlDialect` ABC + `DuckDBDialect` + `SnowflakeDialect`; all SQL generation and numeric-type classification.
- `src/dvi/warehouse/sql_source.py` — `SqlProfileSource`; runs dialect SQL via the executor and adapts rows into `ColumnProfile`.
- `src/dvi/pipeline/analyze.py` — add `detect_symptoms_from_profiles` + `analyze_change_from_profiles`; refactor `detect_symptoms` to delegate.
- `src/dvi/pipeline/__init__.py` — export the two new entries.
- `tests/test_warehouse_dialect.py` — dialect SQL-generation + `is_numeric_type` tests (both dialects).
- `tests/test_warehouse_sql_source.py` — `SqlProfileSource` field-parity + edge-case tests, executed against in-process DuckDB.
- `tests/test_pushdown_equivalence.py` — cross-engine detection-equivalence (headline proof).
- `docs/warehouse-pushdown.md` — new; Snowflake wiring + usage.
- `README.md`, `CHANGELOG.md`, `docs/architecture.md`, `src/dvi/profiling/profiler.py` (docstring) — doc/roadmap updates.

---

### Task 1: `SqlDialect` ABC + `DuckDBDialect`

**Files:**
- Create: `src/dvi/warehouse/__init__.py`
- Create: `src/dvi/warehouse/dialect.py`
- Test: `tests/test_warehouse_dialect.py`

**Interfaces:**
- Consumes: nothing (new package).
- Produces:
  - `class SqlDialect(ABC)` with `name: str`; methods `types_query(self, table: str) -> str`, `is_numeric_type(self, type_string: str) -> bool`, `aggregate_query(self, table: str, column: str, *, numeric: bool) -> str`, `topk_query(self, table: str, column: str, top_k: int) -> str`.
  - Module constant `QUANTILES: tuple[tuple[str, str], ...] = (("p05", "0.05"), ("p25", "0.25"), ("p50", "0.5"), ("p75", "0.75"), ("p95", "0.95"))` — name → SQL fraction literal, consumed by Task 3's adapter for column ordering.
  - `class DuckDBDialect(SqlDialect)` with `name = "duckdb"`.
  - Aggregate query column order (numeric): `row_count, null_count, distinct_count, numeric_count, mean, stddev, minimum, maximum, p05, p25, p50, p75, p95` (13 columns). Non-numeric: `row_count, null_count, distinct_count` (3 columns).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_warehouse_dialect.py`:

```python
from dvi.warehouse import DuckDBDialect


def test_duckdb_types_query():
    d = DuckDBDialect()
    assert d.types_query("orders") == "DESCRIBE SELECT * FROM orders"


def test_duckdb_is_numeric_type():
    d = DuckDBDialect()
    assert d.is_numeric_type("BIGINT")
    assert d.is_numeric_type("DOUBLE")
    assert d.is_numeric_type("DECIMAL(18,3)")  # parametrized type
    assert not d.is_numeric_type("VARCHAR")
    assert not d.is_numeric_type("DATE")


def test_duckdb_non_numeric_aggregate_query():
    d = DuckDBDialect()
    sql = d.aggregate_query("orders", "country", numeric=False)
    assert sql == (
        'SELECT COUNT(*) AS row_count, '
        'COUNT(*) - COUNT("country") AS null_count, '
        'COUNT(DISTINCT "country") AS distinct_count '
        'FROM orders'
    )


def test_duckdb_numeric_aggregate_query():
    d = DuckDBDialect()
    sql = d.aggregate_query("orders", "amount", numeric=True)
    assert sql == (
        'SELECT COUNT(*) AS row_count, '
        'COUNT(*) - COUNT("amount") AS null_count, '
        'COUNT(DISTINCT "amount") AS distinct_count, '
        'COUNT(CASE WHEN isfinite("amount") THEN "amount" END) AS numeric_count, '
        'AVG(CASE WHEN isfinite("amount") THEN "amount" END) AS mean, '
        'STDDEV_SAMP(CASE WHEN isfinite("amount") THEN "amount" END) AS stddev, '
        'MIN(CASE WHEN isfinite("amount") THEN "amount" END) AS minimum, '
        'MAX(CASE WHEN isfinite("amount") THEN "amount" END) AS maximum, '
        'QUANTILE_CONT(CASE WHEN isfinite("amount") THEN "amount" END, 0.05) AS p05, '
        'QUANTILE_CONT(CASE WHEN isfinite("amount") THEN "amount" END, 0.25) AS p25, '
        'QUANTILE_CONT(CASE WHEN isfinite("amount") THEN "amount" END, 0.5) AS p50, '
        'QUANTILE_CONT(CASE WHEN isfinite("amount") THEN "amount" END, 0.75) AS p75, '
        'QUANTILE_CONT(CASE WHEN isfinite("amount") THEN "amount" END, 0.95) AS p95 '
        'FROM orders'
    )


def test_duckdb_topk_query():
    d = DuckDBDialect()
    sql = d.topk_query("orders", "country", 50)
    assert sql == (
        'SELECT CAST("country" AS VARCHAR) AS value, COUNT(*) AS n '
        'FROM orders WHERE "country" IS NOT NULL '
        'GROUP BY "country" ORDER BY n DESC, value ASC LIMIT 50'
    )


def test_duckdb_identifier_quoting_escapes_embedded_quote():
    d = DuckDBDialect()
    sql = d.topk_query("orders", 'we"ird', 10)
    assert '"we""ird"' in sql
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/Scripts/activate && pytest tests/test_warehouse_dialect.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'dvi.warehouse'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/dvi/warehouse/dialect.py`:

```python
"""SQL dialects: emit the per-column profiling SQL for a warehouse engine.

Each dialect produces three query shapes for one column: a table-level type
query, a one-row aggregate query (row/null/distinct plus — for numeric columns —
finite-only mean/stddev/min/max/quantiles), and a top-k value-frequency query.
The generated SQL is a string; execution is the caller's job (see
``SqlProfileSource``), so a dialect can be unit-tested without a live warehouse.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

# name -> SQL fraction literal. Order fixes the aggregate-query column layout that
# the SqlProfileSource adapter reads back positionally.
QUANTILES: tuple[tuple[str, str], ...] = (
    ("p05", "0.05"),
    ("p25", "0.25"),
    ("p50", "0.5"),
    ("p75", "0.75"),
    ("p95", "0.95"),
)


class SqlDialect(ABC):
    """Emits profiling SQL for one warehouse engine."""

    name: str
    _NUMERIC_TYPES: frozenset[str]

    @staticmethod
    def _quote(ident: str) -> str:
        """Double-quote an identifier, escaping embedded double quotes."""
        return '"' + ident.replace('"', '""') + '"'

    def is_numeric_type(self, type_string: str) -> bool:
        """Classify a dialect type string as numeric (drives numeric stats)."""
        base = type_string.split("(")[0].strip().upper()
        return base in self._NUMERIC_TYPES

    @abstractmethod
    def types_query(self, table: str) -> str:
        """SQL returning (column_name, type_string) rows for ``table``."""

    @abstractmethod
    def _finite_predicate(self, qcol: str) -> str:
        """Boolean SQL that is true for finite (non-NaN, non-inf) values."""

    @abstractmethod
    def _quantile_term(self, cond: str, name: str, frac: str) -> str:
        """A single quantile projection: <expr> AS <name>."""

    def aggregate_query(self, table: str, column: str, *, numeric: bool) -> str:
        qcol = self._quote(column)
        parts = [
            "COUNT(*) AS row_count",
            f"COUNT(*) - COUNT({qcol}) AS null_count",
            f"COUNT(DISTINCT {qcol}) AS distinct_count",
        ]
        if numeric:
            cond = f"CASE WHEN {self._finite_predicate(qcol)} THEN {qcol} END"
            parts += [
                f"COUNT({cond}) AS numeric_count",
                f"AVG({cond}) AS mean",
                f"STDDEV_SAMP({cond}) AS stddev",
                f"MIN({cond}) AS minimum",
                f"MAX({cond}) AS maximum",
            ]
            parts += [self._quantile_term(cond, name, frac) for name, frac in QUANTILES]
        return f"SELECT {', '.join(parts)} FROM {table}"

    def topk_query(self, table: str, column: str, top_k: int) -> str:
        qcol = self._quote(column)
        return (
            f"SELECT CAST({qcol} AS VARCHAR) AS value, COUNT(*) AS n "
            f"FROM {table} WHERE {qcol} IS NOT NULL "
            f"GROUP BY {qcol} ORDER BY n DESC, value ASC LIMIT {top_k}"
        )


class DuckDBDialect(SqlDialect):
    name = "duckdb"
    _NUMERIC_TYPES = frozenset(
        {
            "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT",
            "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT",
            "FLOAT", "DOUBLE", "REAL", "DECIMAL", "NUMERIC",
        }
    )

    def types_query(self, table: str) -> str:
        return f"DESCRIBE SELECT * FROM {table}"

    def _finite_predicate(self, qcol: str) -> str:
        return f"isfinite({qcol})"

    def _quantile_term(self, cond: str, name: str, frac: str) -> str:
        return f"QUANTILE_CONT({cond}, {frac}) AS {name}"
```

Create `src/dvi/warehouse/__init__.py`:

```python
"""Warehouse pushdown: compute a ColumnProfile in-warehouse via SQL."""

from .dialect import DuckDBDialect, SqlDialect, SnowflakeDialect
from .sql_source import SqlProfileSource

__all__ = ["SqlDialect", "DuckDBDialect", "SnowflakeDialect", "SqlProfileSource"]
```

> NOTE: `__init__.py` imports `SnowflakeDialect` (Task 2) and `SqlProfileSource` (Task 3), which do not exist yet. To keep Task 1 runnable in isolation, temporarily import only `DuckDBDialect`/`SqlDialect` here and expand the imports in Tasks 2 and 3. If executing tasks in order without running the package import between them, you may write the full `__init__.py` now and expect Task 1's dialect tests (which import only `DuckDBDialect`) to still fail on the missing `sql_source`/`SnowflakeDialect` module — so prefer the incremental import. Incremental Task-1 `__init__.py`:

```python
"""Warehouse pushdown: compute a ColumnProfile in-warehouse via SQL."""

from .dialect import DuckDBDialect, SqlDialect

__all__ = ["SqlDialect", "DuckDBDialect"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/Scripts/activate && pytest tests/test_warehouse_dialect.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Lint**

Run: `source .venv/Scripts/activate && ruff check src/dvi/warehouse tests/test_warehouse_dialect.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/dvi/warehouse/__init__.py src/dvi/warehouse/dialect.py tests/test_warehouse_dialect.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
  commit -m "feat(warehouse): SqlDialect ABC and DuckDB dialect SQL generation" \
  --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 2: `SnowflakeDialect`

**Files:**
- Modify: `src/dvi/warehouse/dialect.py`
- Modify: `src/dvi/warehouse/__init__.py` (add `SnowflakeDialect` to imports + `__all__`)
- Test: `tests/test_warehouse_dialect.py` (add cases)

**Interfaces:**
- Consumes: `SqlDialect` base (Task 1) — same four public methods, same 13/3-column aggregate layout, same `QUANTILES` order.
- Produces: `class SnowflakeDialect(SqlDialect)` with `name = "snowflake"`. Uses `DESCRIBE TABLE` for types, `PERCENTILE_CONT(frac) WITHIN GROUP (ORDER BY <cond>)` for quantiles, and a non-finite exclusion predicate `<qcol> NOT IN ('NaN'::FLOAT, 'inf'::FLOAT, '-inf'::FLOAT)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_warehouse_dialect.py`:

```python
from dvi.warehouse import SnowflakeDialect


def test_snowflake_types_query():
    d = SnowflakeDialect()
    assert d.types_query("orders") == "DESCRIBE TABLE orders"


def test_snowflake_is_numeric_type():
    d = SnowflakeDialect()
    assert d.is_numeric_type("NUMBER(38,0)")
    assert d.is_numeric_type("FLOAT")
    assert d.is_numeric_type("DOUBLE PRECISION")
    assert not d.is_numeric_type("VARCHAR(16777216)")
    assert not d.is_numeric_type("TIMESTAMP_NTZ")


def test_snowflake_non_numeric_aggregate_query():
    d = SnowflakeDialect()
    sql = d.aggregate_query("orders", "country", numeric=False)
    assert sql == (
        'SELECT COUNT(*) AS row_count, '
        'COUNT(*) - COUNT("country") AS null_count, '
        'COUNT(DISTINCT "country") AS distinct_count '
        'FROM orders'
    )


def test_snowflake_numeric_aggregate_query():
    d = SnowflakeDialect()
    sql = d.aggregate_query("orders", "amount", numeric=True)
    cond = (
        'CASE WHEN "amount" NOT IN (\'NaN\'::FLOAT, \'inf\'::FLOAT, \'-inf\'::FLOAT) '
        'THEN "amount" END'
    )
    assert sql == (
        'SELECT COUNT(*) AS row_count, '
        'COUNT(*) - COUNT("amount") AS null_count, '
        'COUNT(DISTINCT "amount") AS distinct_count, '
        f'COUNT({cond}) AS numeric_count, '
        f'AVG({cond}) AS mean, '
        f'STDDEV_SAMP({cond}) AS stddev, '
        f'MIN({cond}) AS minimum, '
        f'MAX({cond}) AS maximum, '
        f'PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY {cond}) AS p05, '
        f'PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {cond}) AS p25, '
        f'PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {cond}) AS p50, '
        f'PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {cond}) AS p75, '
        f'PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY {cond}) AS p95 '
        'FROM orders'
    )


def test_snowflake_topk_query_matches_shared_shape():
    d = SnowflakeDialect()
    sql = d.topk_query("orders", "country", 50)
    assert sql == (
        'SELECT CAST("country" AS VARCHAR) AS value, COUNT(*) AS n '
        'FROM orders WHERE "country" IS NOT NULL '
        'GROUP BY "country" ORDER BY n DESC, value ASC LIMIT 50'
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/Scripts/activate && pytest tests/test_warehouse_dialect.py -q`
Expected: FAIL — `ImportError: cannot import name 'SnowflakeDialect'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/dvi/warehouse/dialect.py`:

```python
class SnowflakeDialect(SqlDialect):
    name = "snowflake"
    _NUMERIC_TYPES = frozenset(
        {
            "NUMBER", "DECIMAL", "NUMERIC",
            "INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "BYTEINT",
            "FLOAT", "FLOAT4", "FLOAT8", "DOUBLE", "DOUBLE PRECISION", "REAL",
        }
    )

    def types_query(self, table: str) -> str:
        return f"DESCRIBE TABLE {table}"

    def _finite_predicate(self, qcol: str) -> str:
        # Snowflake lacks isfinite(); exclude the special FLOAT values instead.
        # Snowflake's NaN = NaN is TRUE, so NOT IN correctly drops NaN too.
        return f"{qcol} NOT IN ('NaN'::FLOAT, 'inf'::FLOAT, '-inf'::FLOAT)"

    def _quantile_term(self, cond: str, name: str, frac: str) -> str:
        return f"PERCENTILE_CONT({frac}) WITHIN GROUP (ORDER BY {cond}) AS {name}"
```

Update `src/dvi/warehouse/__init__.py` to include `SnowflakeDialect`:

```python
"""Warehouse pushdown: compute a ColumnProfile in-warehouse via SQL."""

from .dialect import DuckDBDialect, SnowflakeDialect, SqlDialect

__all__ = ["SqlDialect", "DuckDBDialect", "SnowflakeDialect"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/Scripts/activate && pytest tests/test_warehouse_dialect.py -q`
Expected: PASS (11 tests).

- [ ] **Step 5: Lint**

Run: `source .venv/Scripts/activate && ruff check src/dvi/warehouse tests/test_warehouse_dialect.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/dvi/warehouse/dialect.py src/dvi/warehouse/__init__.py tests/test_warehouse_dialect.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
  commit -m "feat(warehouse): Snowflake dialect with SQL-gen tests" \
  --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 3: `SqlProfileSource` (row → `ColumnProfile` adapter, DuckDB-executed)

**Files:**
- Create: `src/dvi/warehouse/sql_source.py`
- Modify: `src/dvi/warehouse/__init__.py` (add `SqlProfileSource`)
- Test: `tests/test_warehouse_sql_source.py`

**Interfaces:**
- Consumes: `SqlDialect`/`DuckDBDialect` (Tasks 1–2); `QUANTILES` from `dvi.warehouse.dialect`; `ColumnProfile`, `NumericStats` from `dvi.profiling`; `DEFAULT_TOP_K` from `dvi.profiling.profiler`.
- Produces:
  - `class SqlProfileSource` — `__init__(self, execute, table, *, dialect, top_k=DEFAULT_TOP_K)` where `execute` is `Callable[[str], Iterable[Sequence]]` (DBAPI `fetchall` shape).
  - `profile(self, columns: list[str] | None = None) -> dict[str, ColumnProfile]`.
  - Unknown column → `ValueError`. Mis-shaped aggregate row → `ValueError`.

The test file needs a helper to materialize a Polars frame into a DuckDB table **without pyarrow** (parameterized `executemany`), plus an `execute` adapter over a DuckDB connection.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_warehouse_sql_source.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/Scripts/activate && pytest tests/test_warehouse_sql_source.py -q`
Expected: FAIL — `ImportError: cannot import name 'SqlProfileSource'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/dvi/warehouse/sql_source.py`:

```python
"""Adapt warehouse SQL results into the same ColumnProfile the Polars path builds.

``SqlProfileSource`` runs a dialect's profiling SQL through a thin
``execute(sql) -> rows`` callable (DBAPI cursor shape: an iterable of row
sequences) and assembles a :class:`ColumnProfile` per column — numeric stats when
the column's type is numeric, else ``numeric=None`` — matching
``dvi.profiling.profiler.profile_column`` field for field.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

from dvi.profiling import ColumnProfile, NumericStats
from dvi.profiling.profiler import DEFAULT_TOP_K

from .dialect import QUANTILES, SqlDialect

# Aggregate-query column layout (see SqlDialect.aggregate_query).
_BASE_COLS = 3            # row_count, null_count, distinct_count
_NUMERIC_COLS = _BASE_COLS + 5 + len(QUANTILES)  # + numeric_count/mean/stddev/min/max + quantiles

Execute = Callable[[str], Iterable[Sequence]]


class SqlProfileSource:
    def __init__(
        self,
        execute: Execute,
        table: str,
        *,
        dialect: SqlDialect,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        self._execute = execute
        self._table = table
        self._dialect = dialect
        self._top_k = top_k

    def _column_types(self) -> dict[str, str]:
        rows = self._execute(self._dialect.types_query(self._table))
        return {row[0]: row[1] for row in rows}

    def profile(self, columns: list[str] | None = None) -> dict[str, ColumnProfile]:
        types = self._column_types()
        if columns is None:
            columns = list(types)
        out: dict[str, ColumnProfile] = {}
        for column in columns:
            if column not in types:
                raise ValueError(
                    f"column {column!r} not found in table {self._table!r}"
                )
            numeric = self._dialect.is_numeric_type(types[column])
            out[column] = self._profile_column(column, numeric)
        return out

    def _profile_column(self, column: str, numeric: bool) -> ColumnProfile:
        agg = list(self._execute(self._dialect.aggregate_query(
            self._table, column, numeric=numeric
        )))
        expected = _NUMERIC_COLS if numeric else _BASE_COLS
        if len(agg) != 1 or len(agg[0]) != expected:
            raise ValueError(
                f"unexpected aggregate row shape for {column!r}: "
                f"expected 1 row of {expected} columns"
            )
        row = agg[0]
        row_count, null_count, distinct_count = int(row[0]), int(row[1]), int(row[2])

        numeric_stats = None
        if numeric:
            numeric_count = int(row[3]) if row[3] is not None else 0
            if numeric_count > 0:
                stddev = row[5]
                quantiles = {
                    name: float(row[_BASE_COLS + 5 + i])
                    for i, (name, _) in enumerate(QUANTILES)
                }
                numeric_stats = NumericStats(
                    count=numeric_count,
                    mean=float(row[4]),
                    stddev=float(stddev) if stddev is not None else 0.0,
                    minimum=float(row[6]),
                    maximum=float(row[7]),
                    quantiles=quantiles,
                )

        top_k: dict[str, int] = {}
        for value, count in self._execute(
            self._dialect.topk_query(self._table, column, self._top_k)
        ):
            top_k[str(value)] = int(count)

        return ColumnProfile(
            name=column,
            row_count=row_count,
            null_count=null_count,
            distinct_count=distinct_count,
            top_k=top_k,
            numeric=numeric_stats,
        )
```

Update `src/dvi/warehouse/__init__.py`:

```python
"""Warehouse pushdown: compute a ColumnProfile in-warehouse via SQL."""

from .dialect import DuckDBDialect, SnowflakeDialect, SqlDialect
from .sql_source import SqlProfileSource

__all__ = ["SqlDialect", "DuckDBDialect", "SnowflakeDialect", "SqlProfileSource"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/Scripts/activate && pytest tests/test_warehouse_sql_source.py -q`
Expected: PASS (7 tests).

- [ ] **Step 5: Lint**

Run: `source .venv/Scripts/activate && ruff check src/dvi/warehouse tests/test_warehouse_sql_source.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/dvi/warehouse/sql_source.py src/dvi/warehouse/__init__.py tests/test_warehouse_sql_source.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
  commit -m "feat(warehouse): SqlProfileSource adapts SQL rows into ColumnProfile" \
  --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 4: Analysis seam — `detect_symptoms_from_profiles` + `analyze_change_from_profiles`

**Files:**
- Modify: `src/dvi/pipeline/analyze.py`
- Modify: `src/dvi/pipeline/__init__.py`
- Test: `tests/test_pipeline_from_profiles.py` (create)

**Interfaces:**
- Consumes: existing `_build_detectors`, `_apply_precedence`, `attach_confidence`, `profile_column`, `rank_root_causes`, `synthesize_incident`, `Observation` (all already in `analyze.py`); `ColumnProfile` from `dvi.profiling`.
- Produces:
  - `detect_symptoms_from_profiles(before: dict[str, ColumnProfile], after: dict[str, ColumnProfile], columns: list[str] | None = None, *, dist_threshold=DEFAULT_DISTRIBUTION_THRESHOLD, model=None) -> list[Symptom]`.
  - `analyze_change_from_profiles(*, asset: str, before: dict[str, ColumnProfile], after: dict[str, ColumnProfile], observed_at: datetime, lineage: LineageGraph, changes: list[ChangeEvent], columns=None, model=None) -> Incident | None`.
  - `detect_symptoms` (existing signature unchanged) now delegates to `detect_symptoms_from_profiles` — behavior identical.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pipeline_from_profiles.py`:

```python
from datetime import datetime

import polars as pl

from dvi.incidents import Incident
from dvi.lineage import LineageGraph
from dvi.pipeline import (
    analyze_change,
    analyze_change_from_profiles,
    detect_symptoms,
    detect_symptoms_from_profiles,
)
from dvi.profiling import profile_column
from dvi.rca import ChangeEvent

ASSET = "model.shop.fact_orders"


def _lineage() -> LineageGraph:
    g = LineageGraph()
    g.add_edge(ASSET, "model.shop.revenue_daily")
    return g


def _profiles(df: pl.DataFrame) -> dict:
    return {c: profile_column(df[c].rename(c)) for c in df.columns}


def test_detect_symptoms_from_profiles_matches_dataframe_path():
    before = pl.DataFrame({"country": ["UK"] * 200 + ["US"] * 800})
    after = pl.DataFrame({"country": ["United Kingdom"] * 200 + ["US"] * 800})

    from_df = detect_symptoms(before, after, ["country"])
    from_prof = detect_symptoms_from_profiles(_profiles(before), _profiles(after), ["country"])

    assert [s.signature for s in from_df] == [s.signature for s in from_prof]
    assert [s.column for s in from_df] == [s.column for s in from_prof]
    assert from_prof[0].from_value == "UK"
    assert from_prof[0].to_value == "United Kingdom"


def test_analyze_change_from_profiles_yields_incident():
    before = pl.DataFrame({"country": ["UK"] * 200 + ["US"] * 800})
    after = pl.DataFrame({"country": ["United Kingdom"] * 200 + ["US"] * 800})
    deploy = ChangeEvent("deploy-1", datetime(2026, 8, 25, 9, 0), [ASSET], "deploy")

    incident = analyze_change_from_profiles(
        asset=ASSET,
        before=_profiles(before),
        after=_profiles(after),
        observed_at=datetime(2026, 8, 25, 9, 5),
        lineage=_lineage(),
        changes=[deploy],
        columns=["country"],
    )

    assert isinstance(incident, Incident)
    assert incident.primary_cause.change.id == "deploy-1"


def test_no_symptoms_returns_none():
    same = pl.DataFrame({"country": ["UK"] * 200 + ["US"] * 800})
    incident = analyze_change_from_profiles(
        asset=ASSET,
        before=_profiles(same),
        after=_profiles(same),
        observed_at=datetime(2026, 8, 25, 9, 5),
        lineage=_lineage(),
        changes=[],
        columns=["country"],
    )
    assert incident is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/Scripts/activate && pytest tests/test_pipeline_from_profiles.py -q`
Expected: FAIL — `ImportError: cannot import name 'analyze_change_from_profiles'`.

- [ ] **Step 3: Write minimal implementation**

In `src/dvi/pipeline/analyze.py`, add an import for the profile type near the top (with the other `dvi` imports):

```python
from dvi.profiling import ColumnProfile, profile_column
```

(Replace the existing `from dvi.profiling import profile_column` line.)

Add `detect_symptoms_from_profiles` and refactor `detect_symptoms` to delegate. Replace the current `detect_symptoms` body with:

```python
def detect_symptoms_from_profiles(
    before: dict[str, ColumnProfile],
    after: dict[str, ColumnProfile],
    columns: list[str] | None = None,
    *,
    dist_threshold: float = DEFAULT_DISTRIBUTION_THRESHOLD,
    model: LogisticModel | None = None,
):
    """Run every active detector over already-computed profiles.

    This is the shared detection core: both the local Polars path and the
    warehouse pushdown path funnel through here, so they cannot diverge.
    """
    if columns is None:
        columns = [c for c in before if c in after]

    detectors = _build_detectors(dist_threshold)
    symptoms = []
    for column in columns:
        baseline, current = before[column], after[column]
        for detector in detectors:
            symptom = detector(baseline, current)
            if symptom is not None:
                symptoms.append(symptom)

    survivors = _apply_precedence(symptoms)
    if model is not None:
        survivors = [
            attach_confidence(s, before[s.column], after[s.column], model)
            for s in survivors
        ]
    return survivors


def detect_symptoms(
    before: pl.DataFrame,
    after: pl.DataFrame,
    columns: list[str] | None = None,
    *,
    dist_threshold: float = DEFAULT_DISTRIBUTION_THRESHOLD,
    model: LogisticModel | None = None,
):
    """Profile the given columns before/after and run every active detector.

    When ``model`` is supplied, each surviving symptom is annotated with a
    measured ``confidence``; otherwise ``confidence`` stays ``None`` (M1/M2
    behavior unchanged).
    """
    if columns is None:
        columns = [c for c in before.columns if c in after.columns]

    before_profiles = {c: profile_column(before[c].rename(c)) for c in columns}
    after_profiles = {c: profile_column(after[c].rename(c)) for c in columns}
    return detect_symptoms_from_profiles(
        before_profiles, after_profiles, columns,
        dist_threshold=dist_threshold, model=model,
    )
```

Add `analyze_change_from_profiles` after `analyze_change`:

```python
def analyze_change_from_profiles(
    *,
    asset: str,
    before: dict[str, ColumnProfile],
    after: dict[str, ColumnProfile],
    observed_at: datetime,
    lineage: LineageGraph,
    changes: list[ChangeEvent],
    columns: list[str] | None = None,
    model: LogisticModel | None = None,
) -> Incident | None:
    """Analyze a before/after pair of column profiles and return an incident.

    The warehouse-pushdown twin of :func:`analyze_change`: it takes profiles
    already computed in-warehouse instead of raw DataFrames, then runs the
    identical detection / attribution / synthesis path.
    """
    symptoms = detect_symptoms_from_profiles(before, after, columns, model=model)
    if not symptoms:
        return None

    observations = [Observation(asset, observed_at, s) for s in symptoms]
    ranked = rank_root_causes(observations, changes, lineage)
    return synthesize_incident(ranked, lineage, observations)
```

Update `src/dvi/pipeline/__init__.py`:

```python
"""Pipeline: end-to-end orchestration of the DVI analysis path."""

from .analyze import (
    analyze_change,
    analyze_change_from_profiles,
    detect_symptoms,
    detect_symptoms_from_profiles,
)

__all__ = [
    "analyze_change",
    "analyze_change_from_profiles",
    "detect_symptoms",
    "detect_symptoms_from_profiles",
]
```

- [ ] **Step 4: Run the new tests + the existing pipeline suite (refactor must not regress)**

Run: `source .venv/Scripts/activate && pytest tests/test_pipeline_from_profiles.py tests/test_pipeline_end_to_end.py tests/test_pipeline_detectors.py -q`
Expected: PASS (all).

- [ ] **Step 5: Lint**

Run: `source .venv/Scripts/activate && ruff check src/dvi/pipeline tests/test_pipeline_from_profiles.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/dvi/pipeline/analyze.py src/dvi/pipeline/__init__.py tests/test_pipeline_from_profiles.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
  commit -m "feat(pipeline): profiles-based analysis seam shared by both paths" \
  --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 5: Cross-engine detection-equivalence test (headline proof)

**Files:**
- Test: `tests/test_pushdown_equivalence.py` (create)

**Interfaces:**
- Consumes: `analyze_change` + `analyze_change_from_profiles` (Task 4); `SqlProfileSource` + `DuckDBDialect` (Tasks 1–3); benchmark `make_orders`/`inject_value_substitution` from `dvi.benchmark`.
- Produces: no new production code — this task is the parity assertion that the warehouse path decides identically to the Polars path.

- [ ] **Step 1: Write the failing test**

Create `tests/test_pushdown_equivalence.py`:

```python
"""Headline proof: the warehouse pushdown path yields the SAME incidents as the
local Polars path on the same data — categorical and numeric signatures alike."""

from datetime import datetime

import duckdb
import polars as pl

from dvi.benchmark import inject_value_substitution, make_orders
from dvi.lineage import LineageGraph
from dvi.pipeline import analyze_change, analyze_change_from_profiles
from dvi.warehouse import DuckDBDialect, SqlProfileSource
from dvi.rca import ChangeEvent

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
    ps, us = polars_inc.primary_cause.explained[0].symptom, pushdown_inc.primary_cause.explained[0].symptom
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
```

- [ ] **Step 2: Run test to verify current status**

Run: `source .venv/Scripts/activate && pytest tests/test_pushdown_equivalence.py -q`
Expected: PASS if Tasks 1–4 are complete. If either case fails on a float-formatting or quantile mismatch that changes the *decision*, investigate before proceeding — the parity bar is decision-identity, and a real divergence here is a genuine finding, not a test to relax. (Field-level float drift that does NOT change the decision is acceptable and already covered by epsilon in Task 3.)

- [ ] **Step 3: Lint**

Run: `source .venv/Scripts/activate && ruff check tests/test_pushdown_equivalence.py`
Expected: no errors.

- [ ] **Step 4: Run the FULL suite (guard the whole branch)**

Run: `source .venv/Scripts/activate && pytest -q`
Expected: PASS (all prior tests + the ~24 new warehouse/pipeline tests).

- [ ] **Step 5: Commit**

```bash
git add tests/test_pushdown_equivalence.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
  commit -m "test(warehouse): cross-engine detection equivalence (polars vs duckdb pushdown)" \
  --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 6: Documentation & roadmap updates

**Files:**
- Create: `docs/warehouse-pushdown.md`
- Modify: `src/dvi/profiling/profiler.py` (module docstring)
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/architecture.md`

**Interfaces:** none (docs only). No test step; verification is a full-suite run + manual read.

- [ ] **Step 1: Write `docs/warehouse-pushdown.md`**

Create `docs/warehouse-pushdown.md` covering: the pushdown idea (compute `ColumnProfile` in SQL, pull back only the compact profile); the thin `execute(sql) -> rows` contract; a DuckDB usage example; a Snowflake wiring example (pass a Snowflake cursor's `execute`/`fetchall`, dialect=`SnowflakeDialect()`) noting Snowflake SQL is unit-tested but not CI-executed; and the detection-equivalence guarantee. Use this content:

````markdown
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
````

- [ ] **Step 2: Update the profiler docstring**

In `src/dvi/profiling/profiler.py`, replace the M5 roadmap note (lines 3–5) with a delivered-state note:

```python
"""Compute a :class:`ColumnProfile` from column data.

This path profiles an in-memory Polars ``Series``. The warehouse pushdown path
(``dvi.warehouse``) computes the same ``ColumnProfile`` via SQL and pulls back
only the compact result; both producers are held to detection-equivalence.
"""
```

- [ ] **Step 3: Update README, CHANGELOG, architecture**

- `README.md`: mark M5a delivered in the roadmap and add a "Warehouse pushdown profiling" feature bullet linking `docs/warehouse-pushdown.md`; move "Warehouses other than Snowflake" note so it reflects the DuckDB-executed / Snowflake-documented split; bump the test count to the new total (run `pytest -q` and read the count).
- `CHANGELOG.md`: add an M5a section — "Warehouse pushdown profiling: compute `ColumnProfile` in-warehouse via SQL (DuckDB executed, Snowflake dialect + SQL-gen tests); `analyze_change_from_profiles`; cross-engine detection-equivalence."
- `docs/architecture.md`: add a "Warehouse pushdown" subsection describing the `warehouse` package (dialect + `SqlProfileSource`), the thin executor contract, and the shared `detect_symptoms_from_profiles` seam.

(Match each file's existing heading style and formatting. Do not invent version numbers or dates beyond today, 2026-08-29.)

- [ ] **Step 4: Full-suite sanity + doc read-through**

Run: `source .venv/Scripts/activate && pytest -q`
Expected: PASS. Confirm the README test count matches the reported total.

- [ ] **Step 5: Commit**

```bash
git add docs/warehouse-pushdown.md src/dvi/profiling/profiler.py README.md CHANGELOG.md docs/architecture.md
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
  commit -m "docs(m5a): document warehouse pushdown + mark M5a delivered" \
  --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

## Self-Review

**Spec coverage:**
- §2.1 detection-equivalent parity → Task 5 (headline) + Task 3 epsilon field parity. ✓
- §2.2 thin executor callable → Task 3 `execute` param, `SqlProfileSource`. ✓
- §2.3 Snowflake dialect + SQL-gen tests, DuckDB executed → Task 2 (string-assert) + Task 3/5 (DuckDB executed). ✓
- §2.4 parallel `analyze_change_from_profiles` + shared `detect_symptoms_from_profiles` → Task 4. ✓
- §3.1 `SqlDialect` four methods, quantile/stddev/finite/topk specifics → Tasks 1–2. ✓
- §3.2 `SqlProfileSource.profile`, NULL stddev→0.0, empty/all-null→numeric None → Task 3. ✓
- §3.3 analysis seam signatures → Task 4. ✓
- §4 error handling (non-numeric, empty/all-null, unknown column ValueError, stddev n=1, mis-shaped rows) → Task 3 tests. ✓
- §5 testing strategy items 1–6 → Tasks 1–5. ✓
- §6 files touched → all six tasks. ✓
- §7 YAGNI (one query per column, no async/pool, only DuckDB+Snowflake, no sampling, no CLI) → respected; nothing in the plan adds them. ✓

**Placeholder scan:** No TBD/TODO; every code and test step shows real content; the only forward-reference (Task 1 `__init__.py` importing not-yet-existing modules) is called out explicitly with an incremental fallback. ✓

**Type consistency:** `SqlProfileSource(execute, table, *, dialect, top_k)` identical across Tasks 3, 5, and the doc. `profile(columns=None)` consistent. Aggregate layout `_BASE_COLS=3`, `_NUMERIC_COLS=3+5+5=13` matches the dialect's 13-column numeric query and the 13-column string-assertion test. `QUANTILES` order (`p05,p25,p50,p75,p95`) shared by dialect generation and adapter read-back. `detect_symptoms_from_profiles` / `analyze_change_from_profiles` signatures identical in Tasks 4, 5, and `__init__`. ✓
