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
