# M5a — Warehouse pushdown profiling (design)

**Date:** 2026-08-27
**Milestone:** M5a (first half of M5; M5b = CLI + GitHub Action)
**Headline claim:** *Real-user adoption path, part 1* — DVI computes the same
`ColumnProfile` **in the warehouse via SQL**, pulling back only the compact
profile instead of raw rows, and proves the warehouse path produces the **same
incidents** as the local polars path.

## 1. Problem

Today DVI profiles a column by pulling its rows into an in-memory Polars
`Series` and running `profile_column`. For a real warehouse table that means
extracting every row into Python — infeasible at warehouse scale and a
non-starter for adoption. `profiling/profiler.py` already flags the fix: a
"warehouse pushdown path (computing the same profile via SQL, extracting only
the compact result)". `ColumnProfile` is the universal currency — detectors,
calibration, and RCA all consume profiles, never raw rows — so pushdown only
needs to add a *second producer* of `ColumnProfile`, computed in SQL.

## 2. Decisions (locked during brainstorming)

1. **Parity bar: detection-equivalent.** A warehouse-computed profile must yield
   the *same symptoms/incidents* as the polars profile on the same data,
   verified by a cross-engine test. Individual float fields may differ in their
   last digits; the guaranteed invariant is the decision.
2. **Connection model: thin executor callable.** `SqlProfileSource` takes a
   minimal `execute(sql) -> rows` function (DBAPI-cursor shape). DVI builds and
   runs the queries; the caller owns connection and auth. Tested in-process with
   a real DuckDB connection; production passes a Snowflake cursor. No
   DVI-owned connections, no driver dependency, **no pyarrow**.
3. **Snowflake scope: dialect + SQL-gen tests, documented execution.** Ship a
   `SnowflakeDialect` whose emitted SQL is unit-tested by string assertion, plus
   docs for wiring a real cursor. **DuckDB is the CI-executed reference.** This
   proves the abstraction generalizes without needing the (pyarrow-pulling)
   Snowflake driver in CI.
4. **Analysis seam: a parallel profiles-dict entry.** Add
   `analyze_change_from_profiles(...)` alongside the untouched polars
   `analyze_change`. `detect_symptoms` is refactored to delegate to a new
   `detect_symptoms_from_profiles`, so both paths share one code path with **zero
   behavior change** to the local path.

## 3. Architecture

New package `src/dvi/warehouse/`:

- `dialect.py` — `SqlDialect` (abstract) + `DuckDBDialect`, `SnowflakeDialect`.
  A dialect emits the profiling SQL for one column and classifies column types.
- `sql_source.py` — `SqlProfileSource`, which runs a dialect's queries through
  the executor callable and adapts result rows into `ColumnProfile`.

The existing `pipeline/analyze.py` gains the parallel profiles-based entry.
Everything downstream of profiling (detectors, precedence, calibration, RCA,
incident synthesis) is unchanged and shared by both paths.

### 3.1 `SqlDialect`

```python
class SqlDialect(ABC):
    name: str  # "duckdb" | "snowflake"

    def types_query(self, table: str) -> str:
        """SQL returning (column_name, type_string) rows for `table`."""

    def is_numeric_type(self, type_string: str) -> bool:
        """Classify a dialect type string as numeric (drives numeric stats)."""

    def aggregate_query(self, table: str, column: str, *, numeric: bool) -> str:
        """One-row query: row_count, null_count, distinct_count, and — when
        `numeric` — count/mean/stddev(sample)/min/max/p05/p25/p50/p75/p95 over
        finite non-null values."""

    def topk_query(self, table: str, column: str, top_k: int) -> str:
        """(value_as_text, count) rows for the top_k most frequent non-null
        values, ordered (count desc, value asc)."""
```

Dialect specifics:

- **Quantiles:** DuckDB `QUANTILE_CONT(col, q)`; Snowflake
  `PERCENTILE_CONT(q) WITHIN GROUP (ORDER BY col)`. Both linear-interpolating,
  matching the polars `interpolation="linear"` profiler.
- **Std dev:** `STDDEV_SAMP` (sample, ddof=1) in both, matching polars `.std()`.
  Returns NULL at n=1 → adapter maps to `0.0`.
- **Finite filter (floats):** the aggregate query restricts numeric stats to
  `col IS NOT NULL` and finite values (DuckDB `isfinite(col)`; Snowflake
  `NOT (col != col) AND col NOT IN ('inf','-inf'::float)` equivalent), mirroring
  the profiler dropping non-finite floats so one dirty cell cannot fabricate a
  distribution.
- **top_k value cast:** `CAST(col AS VARCHAR)` so keys are strings, matching the
  profiler's `str(value)`; ordering `(count desc, value_text asc)` matches the
  profiler's deterministic re-sort.

### 3.2 `SqlProfileSource`

```python
class SqlProfileSource:
    def __init__(self, execute, table, *, dialect, top_k=DEFAULT_TOP_K): ...
    def profile(self, columns: list[str] | None = None) -> dict[str, ColumnProfile]:
        """Profile each column into the same ColumnProfile the polars path builds.

        Runs one types_query for the table, then per column an aggregate_query
        and a topk_query, adapting rows into ColumnProfile. When columns is None,
        profiles every column returned by the types query."""
```

- `execute(sql)` returns an iterable of row sequences (DBAPI `fetchall` shape).
- Column type is taken from the one-shot types query; numeric columns get the
  numeric aggregate branch, others get `numeric=None`.
- The adapter builds `ColumnProfile` field-for-field the way `profiler.py` does
  (NULL stddev → `0.0`; empty/all-null → `distinct_count=0`, empty `top_k`,
  `numeric=None`).

### 3.3 Analysis seam

```python
def detect_symptoms_from_profiles(
    before: dict[str, ColumnProfile],
    after: dict[str, ColumnProfile],
    columns: list[str] | None = None,
    *, dist_threshold=DEFAULT_DISTRIBUTION_THRESHOLD, model=None,
): ...

def analyze_change_from_profiles(
    *, asset, before, after,           # before/after: dict[str, ColumnProfile]
    observed_at, lineage, changes, columns=None, model=None,
) -> Incident | None: ...
```

`detect_symptoms(before_df, after_df, ...)` is refactored to profile each column
into two dicts and then call `detect_symptoms_from_profiles`, so the polars path
and the pushdown path run identical detection/precedence/calibration logic.

### 3.4 Data flow (pushdown)

```
SqlProfileSource(execute, before_table, dialect=d).profile(cols)  -> before: dict
SqlProfileSource(execute, after_table,  dialect=d).profile(cols)  -> after:  dict
analyze_change_from_profiles(asset=..., before=before, after=after,
                             observed_at=..., lineage=..., changes=...) -> Incident|None
```

## 4. Error handling

Mirror the polars path so the two producers are interchangeable:

- **Non-numeric column** → `numeric=None`; numeric aggregates not emitted.
- **Empty table / all-null column** → `distinct_count=0`, empty `top_k`,
  `numeric=None`.
- **Unknown column** (absent from the types query) → `ValueError` naming the
  column and table (not a raw DB error).
- **Float stddev at n=1** → SQL NULL mapped to `0.0`.
- **Mis-shaped `execute` result** → a clear adapter error, not an `IndexError`.

## 5. Testing strategy

Strict TDD (RED-GREEN-REFACTOR), matching repo style. DuckDB is available and
executes in-process; Snowflake is SQL-gen only.

1. **Dialect SQL generation** — assert the exact SQL emitted by `DuckDBDialect`
   and `SnowflakeDialect` for `types_query`, `aggregate_query` (numeric and
   non-numeric), and `topk_query`. This is how Snowflake is verified without a
   driver.
2. **`is_numeric_type`** — per dialect, numeric vs non-numeric type strings.
3. **`SqlProfileSource` field parity (DuckDB, in-process)** — for a known table,
   the adapted `ColumnProfile` matches `profile_column` on the same data: exact
   on row/null/distinct/top_k, within a tight epsilon on mean/stddev/quantiles.
4. **Edge cases** — empty table, all-null column, single-row numeric (stddev
   `0.0`), non-numeric column (`numeric=None`), unknown column (`ValueError`).
5. **Cross-engine detection equivalence (headline proof)** — build before/after
   datasets in polars, load the same rows into DuckDB, run `analyze_change`
   (polars) and `analyze_change_from_profiles` (DuckDB pushdown), and assert the
   incidents are decision-identical (same signature, column, severity, business
   impact, affected assets). Cover categorical signatures (value-substitution,
   case-format) and numeric signatures (distribution-shift, unit-scale).
6. **`detect_symptoms` refactor** — existing detection tests stay green,
   proving the polars path is behavior-identical after delegating to
   `detect_symptoms_from_profiles`.

## 6. Files touched

- `src/dvi/warehouse/__init__.py` — new: exports `SqlDialect`, `DuckDBDialect`,
  `SnowflakeDialect`, `SqlProfileSource`.
- `src/dvi/warehouse/dialect.py` — new: dialects + SQL generation.
- `src/dvi/warehouse/sql_source.py` — new: `SqlProfileSource` + row→profile adapter.
- `src/dvi/pipeline/analyze.py` — add `detect_symptoms_from_profiles`,
  `analyze_change_from_profiles`; refactor `detect_symptoms` to delegate.
- `src/dvi/pipeline/__init__.py` — export the new entries if the package exports
  the existing ones.
- `src/dvi/profiling/profiler.py` — update the M5 docstring note to point at the
  delivered `warehouse` package.
- Tests: `tests/test_warehouse_dialect.py`, `tests/test_warehouse_sql_source.py`,
  `tests/test_pushdown_equivalence.py`, plus additions to the detection/pipeline
  tests for the refactor.
- Docs: `docs/warehouse-pushdown.md` (new, Snowflake wiring), `README.md`
  (M5a status + pushdown note), `CHANGELOG.md` (M5a section),
  `docs/architecture.md` (warehouse section).

## 7. Out of scope (YAGNI)

- Batching / single-query-per-table optimization (one aggregate + one top-k
  query per column, for correctness and parity clarity first).
- Async execution, connection pooling, DVI-owned connections/credentials.
- Dialects beyond DuckDB + Snowflake (Postgres etc. later via the same seam).
- Sampling / approximate profiling / incremental scans.
- CLI and GitHub Action — that is M5b.
