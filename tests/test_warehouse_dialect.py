from dvi.warehouse import DuckDBDialect, SnowflakeDialect


def test_duckdb_types_query():
    d = DuckDBDialect()
    assert d.types_query("orders") == 'DESCRIBE SELECT * FROM "orders"'


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
        'FROM "orders"'
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
        'FROM "orders"'
    )


def test_duckdb_topk_query():
    d = DuckDBDialect()
    sql = d.topk_query("orders", "country", 50)
    assert sql == (
        'SELECT CAST("country" AS VARCHAR) AS value, COUNT(*) AS n '
        'FROM "orders" WHERE "country" IS NOT NULL '
        'GROUP BY "country" ORDER BY n DESC, value ASC LIMIT 50'
    )


def test_duckdb_identifier_quoting_escapes_embedded_quote():
    d = DuckDBDialect()
    sql = d.topk_query("orders", 'we"ird', 10)
    assert '"we""ird"' in sql


def test_snowflake_types_query():
    d = SnowflakeDialect()
    assert d.types_query("orders") == 'DESCRIBE TABLE "orders"'


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
        'FROM "orders"'
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
        'FROM "orders"'
    )


def test_snowflake_topk_query_matches_shared_shape():
    d = SnowflakeDialect()
    sql = d.topk_query("orders", "country", 50)
    assert sql == (
        'SELECT CAST("country" AS VARCHAR) AS value, COUNT(*) AS n '
        'FROM "orders" WHERE "country" IS NOT NULL '
        'GROUP BY "country" ORDER BY n DESC, value ASC LIMIT 50'
    )


def test_duckdb_qualified_table_quoted_per_part():
    d = DuckDBDialect()
    assert d.types_query("analytics.orders") == 'DESCRIBE SELECT * FROM "analytics"."orders"'
    agg = d.aggregate_query("analytics.orders", "country", numeric=False)
    assert agg.endswith('FROM "analytics"."orders"')
    topk = d.topk_query("analytics.orders", "country", 10)
    assert 'FROM "analytics"."orders" WHERE' in topk


def test_snowflake_qualified_table_quoted_per_part():
    d = SnowflakeDialect()
    assert d.types_query("db.schema.orders") == 'DESCRIBE TABLE "db"."schema"."orders"'
    agg = d.aggregate_query("db.schema.orders", "country", numeric=False)
    assert agg.endswith('FROM "db"."schema"."orders"')


def test_table_identifier_injection_rendered_inert():
    # A malicious table name must be quoted into a single (unresolvable) identifier,
    # not interpolated as raw SQL that could break out of the FROM clause.
    d = DuckDBDialect()
    sql = d.types_query('orders"; DROP TABLE users --')
    assert sql == 'DESCRIBE SELECT * FROM "orders""; DROP TABLE users --"'
    # The dangerous tokens are inside a quoted identifier, so no second statement exists.
    assert not sql.rstrip().endswith("--")
