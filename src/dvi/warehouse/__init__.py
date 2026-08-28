"""Warehouse pushdown: compute a ColumnProfile in-warehouse via SQL."""

from .dialect import DuckDBDialect, SnowflakeDialect, SqlDialect

__all__ = ["SqlDialect", "DuckDBDialect", "SnowflakeDialect"]
