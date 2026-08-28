"""Warehouse pushdown: compute a ColumnProfile in-warehouse via SQL."""

from .dialect import DuckDBDialect, SqlDialect

__all__ = ["SqlDialect", "DuckDBDialect"]
