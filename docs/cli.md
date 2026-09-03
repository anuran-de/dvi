# DVI CLI + GitHub Action

DVI runs its semantic-change detectors over a before/after snapshot of one
asset, declared in a single `dvi.toml`, and reports an incident (or a clean
bill of health) as Markdown + JSON. A thin GitHub Action posts that report as a
sticky pull-request comment and fails the check when the incident is severe
enough.

## Install

```bash
pip install dvi          # provides the `dvi` command
```

## Configure — `dvi.toml`

```toml
asset = "model.shop.fct_orders"           # the asset being analyzed
columns = ["revenue", "country"]          # optional; omit = all shared columns

[source]                                  # exactly one shape, keyed by `kind`
kind = "file"                             # "file" | "warehouse"
before = "artifacts/fct_orders.main.parquet"
after  = "artifacts/fct_orders.pr.parquet"
# --- OR ---
# kind = "warehouse"
# database = "warehouse.duckdb"
# before_table = "prod.fct_orders"
# after_table  = "pr.fct_orders"

[lineage]
manifest = "target/manifest.json"         # dbt manifest → models + exposures

[[changes]]                               # optional; RCA attributes to these too
id = "pr-1234"
label = "Refactor revenue rollup"
targets = ["model.shop.stg_orders"]       # must be nodes in the manifest
timestamp = 2026-08-30T12:00:00Z          # required, ISO-8601

[git]                                      # optional; controls auto-derived changes
base = "main"                              # optional; defaults to $GITHUB_BASE_REF, else HEAD~1
head = "HEAD"                              # optional; defaults to $GITHUB_SHA, else HEAD

[gate]
fail_on = "high"                          # low | medium | high | critical
model = true                              # attach calibrated confidence

[store]                                    # optional; omit to stay stateless
path = ".dvi/incidents.db"                # record incidents for cross-run history
```

- **File source:** `.parquet`, `.csv`, `.ndjson`, read natively by polars.
- **Warehouse source:** a DuckDB database file DVI opens read-only; profiling is
  pushed into SQL (the M5a path). See *Snowflake* below.
- **Table identifiers** (`before_table` / `after_table`) must be plain SQL
  identifiers, optionally dot-qualified (`schema.table`, `db.schema.table`) —
  letters, digits, underscore and `$`, not starting with a digit. Anything else
  (spaces, quotes, semicolons, comment markers) is rejected at config parse. The
  generated SQL also quotes each dotted part (`"schema"."table"`), so a table name
  can never inject SQL into a profiling query.
- **Incident store** (optional `[store]`): when set, each run that finds an
  incident records it to a local SQLite file with a stable identity, so recurring
  incidents dedupe and an asset's history is queryable over time. Omit the section
  to stay fully stateless. Recording never changes the exit code. See
  [Incident store](incident-store.md).
- **Auto-derived change events** (optional `[git]`): in CI, DVI auto-derives
  candidate change events from the commits in the PR range and maps changed
  dbt model files to the assets they touch, so `[[changes]]` is optional.
  Declare `[[changes]]` to add events git can't see (e.g. an upstream vendor
  load); explicit and derived events are unioned and de-duplicated. The range
  resolves as: explicit `[git] base`/`head` → `$GITHUB_BASE_REF`/`$GITHUB_SHA`
  (set automatically on a GitHub Actions pull-request run) → default
  `HEAD~1..HEAD`. If the combined set of change events is empty — none
  declared and none derived — the run raises an error and exits `2`. Deriving
  from history requires the checkout to have full history (see the GitHub
  Action section below); a git problem (no repo, unknown ref) is best-effort
  and simply contributes no derived events rather than failing the run.

## Run

```bash
dvi analyze --config dvi.toml --output-dir .dvi
```

Writes `.dvi/dvi-report.md` and `.dvi/dvi-report.json`, echoes the Markdown, and
exits:

| Exit | Meaning |
|------|---------|
| `0`  | No incident, or an incident below `fail_on`. |
| `1`  | Incident at/above `fail_on` — the gate tripped. |
| `2`  | Could not run (bad config, missing input, unresolved target). |

CI can inject PR-specific paths without rewriting the config:

```bash
dvi analyze --config dvi.toml --source-before prod.parquet --source-after pr.parquet
```

## GitHub Action

```yaml
name: DVI
on:
  pull_request:
permissions:
  contents: read
  pull-requests: write
jobs:
  dvi:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0        # DVI derives change events from commit history
      - uses: anuran-de/dvi@main
        with:
          config: dvi.toml
```

The action installs DVI, runs `dvi analyze`, posts the report as a **sticky**
comment (updated in place on each run, keyed off a hidden `<!-- dvi-report -->`
marker) via the runner's `gh` CLI, and fails the check on the CLI's exit code.
No third-party action is required. The checkout step must use `fetch-depth:
0` (a full clone) — DVI derives candidate change events from the commit
history in the PR range, and a shallow checkout leaves no history to derive
from.

The workflow shipped in this repo (`.github/workflows/dvi-example.yml`) guards
the analysis step on the presence of a `dvi.toml`, so the job stays green until
you add a config — copy it as a starting point and drop in your `dvi.toml`.

## Snowflake

The warehouse source runs against DuckDB out of the box. Snowflake uses the same
`SqlProfileSource` seam with `SnowflakeDialect`; its driver is not exercised in
CI (it pulls `pyarrow`, which DVI avoids), so wire it in your own environment by
constructing the profiles and calling `analyze_change_from_profiles` directly —
see `docs/warehouse-pushdown.md`.
