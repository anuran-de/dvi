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
