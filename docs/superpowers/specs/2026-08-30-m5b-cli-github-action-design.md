# M5b — CLI + GitHub Action PR reports (design)

**Date:** 2026-08-30
**Milestone:** M5b (second half of M5; M5a = warehouse pushdown profiling, delivered)
**Headline claim:** *Real-user adoption path, part 2* — a `dvi` CLI runs the
finished detection pipeline over a before/after snapshot declared in one config
file, renders an operator-facing report, and a thin GitHub Action posts that
report as a sticky PR comment and gates the check on severity.

## 1. Problem

DVI's pipeline is complete (`analyze_change` / `analyze_change_from_profiles`
turn two snapshots of an asset into an `Incident | None`), but the only way to
drive it today is Python. Adoption needs a surface a data team wires into CI:
declare what to compare, run one command on a pull request, and see a report on
the PR that blocks the merge when a material semantic change slips through every
structural check. M5b adds that surface — a CLI and a GitHub Action — **without
adding any detection logic**. All meaning-deciding code stays in the pipeline;
`cli/` only assembles inputs and formats outputs.

## 2. Decisions (locked during brainstorming)

1. **Data source: both file and warehouse.** The config's `source` block is a
   discriminated union: `kind = "file"` (two local columnar files read by polars)
   or `kind = "warehouse"` (a DuckDB database file + two table names, driven
   through the M5a pushdown path). The file source runs in CI with zero
   warehouse; the warehouse source exercises M5a end-to-end. Both converge on
   one `Incident | None`.
2. **Changes: explicit in config.** The RCA change list is declared in the
   config, not auto-derived from git or dbt state. Fully deterministic and
   testable; auto-derivation is a later iteration.
3. **Gating: configurable severity gate.** The CLI exits non-zero when the
   incident's severity meets a configurable `fail_on` threshold (default
   `high`); otherwise it posts the report and exits 0.
4. **Config format: TOML via stdlib `tomllib`**, validated by pydantic v2. No
   `pyyaml` runtime dependency. **CLI framework: stdlib `argparse`.** No
   `click`/`typer` dependency.
5. **Warehouse source is DuckDB-backed in practice; Snowflake documented.** The
   CLI opens a DuckDB database file (the dependency DVI already ships) and builds
   the thin `execute` callable for `SqlProfileSource`. Snowflake wiring is
   documented, consistent with the M5a CI split (DuckDB executed, Snowflake
   dialect + SQL-gen tests only).
6. **Single asset per run (v1).** One config analyzes one before/after pair for
   one asset. Multi-asset runs are a later iteration.
7. **Change `timestamp` is required, not defaulted to "now".** A run must be
   fully reproducible.
8. **Calibration model default-on.** Incidents carry measured confidence in
   reports unless `[gate] model = false`.

## 3. Architecture

New package `src/dvi/cli/`, a thin orchestration layer over the finished
pipeline:

```
dvi.toml ──► config.py (tomllib + pydantic) ──► main.py (argparse)
                                                   │
                        ┌──────────────────────────┴───────────────┐
                        ▼                                           ▼
              source kind = "file"                       source kind = "warehouse"
        polars read ─► analyze_change              DuckDB ─► SqlProfileSource ─►
                        (DataFrame path)              analyze_change_from_profiles
                        │                                           │
                        └─────────────► Incident | None ◄───────────┘
                                             │
                                     render.py (Markdown + JSON)
                                             │
                        write artifacts + stdout ─► exit code (gate)
                                             │
                             action.yml ─► sticky PR comment (gh) ─► check status
```

- `config.py` — pydantic models + `tomllib` loader for `dvi.toml`.
- `sources.py` — the two input adapters, each returning `Incident | None`.
- `render.py` — pure `Incident → Markdown` and `Incident → dict` (JSON), plus
  the no-incident report. Reuses `render_business_impact`.
- `main.py` — the `argparse` entrypoint; wired as a `dvi` console-script.
- `action.yml` (repo root) + `.github/workflows/dvi-example.yml` — the Action.

### 3.1 Config schema (`dvi.toml`)

```toml
asset = "fct_orders"                      # the asset being analyzed
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

[[changes]]                               # one or more; RCA attributes to these
id = "pr-1234"
label = "Refactor revenue rollup"
targets = ["fct_orders"]
timestamp = "2026-08-30T12:00:00Z"        # required, ISO-8601

[gate]
fail_on = "high"                          # low | medium | high | critical
model = true                              # attach calibrated confidence
```

Validation rules (pydantic v2):

- `Source` is a discriminated union on `kind`: a `file` source carries
  `before`/`after` paths and rejects table keys; a `warehouse` source carries
  `database`/`before_table`/`after_table` and rejects file keys.
- `changes` is non-empty (no change → no incident is a config smell).
- `fail_on` is constrained to the severity ladder `low < medium < high <
  critical`.
- `timestamp` parses as an aware datetime.
- Each `changes[].targets` name must resolve to a node in the lineage graph;
  an unresolved target is a config error (exit 2), not a silent miss.

### 3.2 Source adapters (`sources.py`)

```python
def incident_from_config(config: DviConfig) -> Incident | None:
    """Dispatch on config.source.kind and return the analyzed incident."""
```

- **File adapter:** dispatch by extension — `.parquet`, `.csv`, `.ndjson` — to
  polars' native readers (no pyarrow). Build the `LineageGraph` from the dbt
  manifest, the `ChangeEvent` list from `config.changes`, load the frozen
  calibration model when `gate.model` is true, then call `analyze_change`.
- **Warehouse adapter:** open the DuckDB database file, build the thin
  `execute(sql) -> rows` callable over its cursor, profile before/after tables
  with `SqlProfileSource`, then call `analyze_change_from_profiles` with the same
  lineage / changes / model.

Both paths share lineage, change, and model construction (factored into small
helpers) so the only difference is *how the profiles are produced* — exactly the
M5a seam.

### 3.3 Rendering (`render.py`)

Pure functions, no I/O:

```python
def render_markdown(incident: Incident | None, *, asset: str,
                    fail_on: str, gate_failed: bool) -> str: ...
def render_json(incident: Incident | None, *, asset: str,
                fail_on: str, gate_failed: bool,
                generated_at: datetime) -> dict: ...
```

- **Markdown** (the sticky comment): a verdict header
  (`🔴 **High-severity semantic change detected**` /
  `✅ **No semantic change detected**`), the incident title + summary, an evidence
  bullet list, affected downstream assets, the business-impact block (via
  `render_business_impact`) when present, and measured confidence when the model
  ran. Ends with a hidden `<!-- dvi-report -->` marker so the Action can find and
  update the same comment. Built with plain f-strings/`join`, no templating dep.
- **JSON** (the machine artifact): a stable, documented schema —
  `{"asset", "severity", "incident": {...} | null, "gate": {"fail_on",
  "failed"}, "generated_at"}`. The exit code is derived from `gate.failed`.
- The **no-incident** case is a first-class rendered report (green comment,
  `incident: null`, exit 0), never an empty string.

### 3.4 CLI entrypoint (`main.py`)

`dvi analyze --config dvi.toml --output-dir <dir> [overrides]`:

1. Parse args; load + validate config (`tomllib` + pydantic).
2. `incident_from_config(config)`.
3. Compute `gate_failed` from the incident severity vs `fail_on`.
4. `render_markdown` / `render_json`; write `<output-dir>/dvi-report.md` and
   `<output-dir>/dvi-report.json`; echo the Markdown to stdout.
5. Return the exit code (§5).

Thin overrides (e.g. `--source-before` / `--source-after`) let CI inject
PR-specific paths without rewriting the config; the config remains the source of
truth. Wired in `pyproject.toml`:

```toml
[project.scripts]
dvi = "dvi.cli.main:main"
```

### 3.5 GitHub Action

A **composite** `action.yml` at repo root (the repo doubles as a usable action):

1. `actions/setup-python` → install DVI.
2. Run `dvi analyze --config <input> --output-dir <tmp>`, capturing its exit
   code without aborting the step.
3. Post `<tmp>/dvi-report.md` as a **sticky** PR comment via the runner's
   preinstalled `gh` CLI, keyed off the `<!-- dvi-report -->` marker
   (`gh pr comment` create-or-edit), using the workflow's `GITHUB_TOKEN`.
4. Re-raise the CLI's exit code so the check passes/fails per the gate.

Inputs: `config` (default `dvi.toml`), `output-dir`, pass-through overrides;
reads `GITHUB_TOKEN` from the environment. `.github/workflows/dvi-example.yml`
gives a copy-pasteable `pull_request` wiring with
`permissions: pull-requests: write`, doubling as living documentation.

No forge lock-in in the core: comment-posting lives only in the Action layer.
The CLI writes files + stdout and returns an exit code, so it runs identically
in GitLab CI, locally, or anywhere.

## 4. Error handling

Mirror the pipeline's "clear error, not a raw traceback" stance; each failure
names the offending file/table/target:

- **Bad TOML / schema violation** → pydantic/`tomllib` error surfaced as a clear
  message (exit 2).
- **Missing or unreadable source file / DuckDB database** → clear error naming
  the path (exit 2).
- **Unresolved change target** (absent from lineage) → clear error naming the
  target (exit 2).
- **Warehouse connection/query failure** → clear error, not a raw DB traceback
  (exit 2).
- **No columns in common / no incident** → clean no-incident report, exit 0.

## 5. Exit codes (the CI contract)

- `0` — ran cleanly; no incident, or an incident below `fail_on`.
- `1` — ran cleanly; incident at/above `fail_on` (gate tripped → block the PR).
- `2` — usage/config/runtime error (could not run). Distinct from `1` so CI can
  tell "DVI found a problem" from "DVI couldn't run."

Severity ordering for the gate: `low < medium < high < critical`.

## 6. Testing strategy

Strict TDD (RED-GREEN-REFACTOR), matching repo style.

1. **Config** (`test_cli_config.py`) — valid file and warehouse configs parse;
   the discriminated union rejects mixed blocks; empty `changes`, invalid
   `fail_on`, missing/unparseable `timestamp` each raise a clear error.
2. **Source adapters** (`test_cli_sources.py`) — the file adapter on two small
   CSVs yields the *same* `Incident` as calling `analyze_change` directly; the
   warehouse adapter on a DuckDB database file yields the same incident (ties
   into the M5a equivalence guarantee). Unresolved-target → error.
3. **Rendering** (`test_cli_render.py`) — snapshot the Markdown for an incident
   and for the no-incident case; assert the JSON schema/keys and the
   `<!-- dvi-report -->` marker; business-impact block appears only when present.
4. **Gate / exit codes** (`test_cli_gate.py`) — a severity × `fail_on` matrix
   maps to the right `gate_failed` / exit code; the exit-2 error paths.
5. **End-to-end CLI** (`test_cli_main.py`) — run `main()` on a fixture config in
   a tmp dir; assert both artifacts written, stdout content, and exit code across
   an incident-found run and a clean run.
6. **Action lint** (`test_action_yml.py`) — a zero-dependency text-structural
   check of `action.yml`: top-level `name`/`description`/`runs` present,
   `using: composite`, the `dvi analyze` invocation present, every declared
   input referenced, and the sticky-comment marker present. (If `yaml` is
   importable in the test env, the plan may upgrade this to a structured parse.)

The honest automated-testing boundary is the CLI: `action.yml` and the example
workflow are YAML that DVI's pytest cannot meaningfully execute, so they are
covered by the structural lint plus the fully-tested CLI beneath them, not by a
faked "Action passed" test.

## 7. Files touched

- `src/dvi/cli/__init__.py` — new: package exports.
- `src/dvi/cli/config.py` — new: pydantic config models + `tomllib` loader.
- `src/dvi/cli/sources.py` — new: file + warehouse adapters → `Incident | None`.
- `src/dvi/cli/render.py` — new: Markdown + JSON renderers.
- `src/dvi/cli/main.py` — new: `argparse` entrypoint + exit-code logic.
- `pyproject.toml` — add `[project.scripts] dvi = "dvi.cli.main:main"`.
- `action.yml` — new: composite GitHub Action.
- `.github/workflows/dvi-example.yml` — new: example wiring.
- Tests: `tests/test_cli_config.py`, `tests/test_cli_sources.py`,
  `tests/test_cli_render.py`, `tests/test_cli_gate.py`, `tests/test_cli_main.py`,
  `tests/test_action_yml.py`.
- Docs: `docs/cli.md` (new: config reference + Action wiring, incl. Snowflake),
  `README.md` (M5b status + usage), `CHANGELOG.md` (M5b section),
  `docs/architecture.md` (CLI/Action subsection).

## 8. Out of scope (YAGNI)

- Auto-deriving changes from git diff or dbt state comparison.
- Multi-asset runs in a single config.
- Warehouses beyond DuckDB executed / Snowflake documented (same `SqlDialect`
  seam extends later).
- Executing dbt or any transformation in CI — DVI compares snapshots it is
  given, it does not build them.
- Forges beyond GitHub (the CLI is forge-neutral; only the Action is
  GitHub-specific).
- Autonomous remediation.
