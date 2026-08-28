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
            parts += [
                self._quantile_term(cond, name, frac)
                for name, frac in QUANTILES
            ]
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
            "TINYINT",
            "SMALLINT",
            "INTEGER",
            "BIGINT",
            "HUGEINT",
            "UTINYINT",
            "USMALLINT",
            "UINTEGER",
            "UBIGINT",
            "FLOAT",
            "DOUBLE",
            "REAL",
            "DECIMAL",
            "NUMERIC",
        }
    )

    def types_query(self, table: str) -> str:
        return f"DESCRIBE SELECT * FROM {table}"

    def _finite_predicate(self, qcol: str) -> str:
        return f"isfinite({qcol})"

    def _quantile_term(self, cond: str, name: str, frac: str) -> str:
        return f"QUANTILE_CONT({cond}, {frac}) AS {name}"


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
