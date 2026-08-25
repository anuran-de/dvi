<h1 align="center">DVI — Data Versioning Intelligence</h1>

<p align="center">
  <em>Catch the data incidents that pass every green check.</em>
</p>

<p align="center">
  <a href="#status"><img alt="status" src="https://img.shields.io/badge/status-M1%20complete-brightgreen"></a>
  <a href="LICENSE"><img alt="license" src="https://img.shields.io/badge/license-MIT-green"></a>
  <img alt="python" src="https://img.shields.io/badge/python-3.11%2B-blue">
</p>

---

## The problem DVI exists to solve

Data pipelines fail differently from software. A pipeline can **execute successfully, keep its schema, meet its freshness SLA, and pass every null/volume check** — and still make the business number silently wrong.

```sql
-- The whole pipeline stays green. The revenue dashboard is now wrong.
- WHERE status = 'completed'
+ WHERE status = 'COMPLETE'
```

```text
Before                         After
country = "UK"                 country = "United Kingdom"
```

Schema unchanged. Row count unchanged. Freshness normal. Yet downstream logic that expects `"UK"` now under-counts a region, and executive revenue drifts by double digits.

Structural/volumetric observability tools do not catch this class of failure, because **nothing structural changed**. DVI is built specifically for it.

## What DVI does

DVI is a self-hostable intelligence layer that sits **on top of** your existing stack (dbt, your warehouse, Git) — it does not replace them. It:

1. **Profiles** each column over time — including *value distributions*, not just counts.
2. **Detects change signatures** — deterministic tests that recognise the statistical fingerprint of a semantic change (e.g. a dominant category's mass collapsing while a new value absorbs it) without needing to "understand" meaning.
3. **Corroborates** a detected change against deployments/commits and downstream lineage, so an isolated blip stays a *symptom* and only a change that correlates with a deploy and propagates downstream becomes an *incident*.
4. **Ranks likely root causes with evidence** — every claim is backed by observable facts, never a fabricated confidence number.

## Design principles

- **Integrate, don't replace.** Reuse dbt's lineage, your warehouse, DuckDB, `sqlglot`. Build only the intelligence layer from scratch.
- **Deterministic first.** Detection and ranking are deterministic and explainable. An LLM, if used at all, only *narrates* evidence — it never decides whether something changed.
- **Evidence before explanation.** Every root-cause claim carries the observable facts that support it.
- **Honest confidence.** No hand-tuned "92%". Confidence is either omitted (rank + evidence) or *calibrated and measured on held-out incidents* (roadmap M3).
- **Symptom ≠ incident.** Corroboration (time × deployment × downstream propagation) is required before anything pages a human — this is how false positives stay low.

## Status

> **M1 — walking skeleton: complete.** The thinnest end-to-end path that proves the core hypothesis works: profile → temporal snapshots → value-substitution detector → dbt lineage → corroboration → ranked root cause with evidence, on synthetic data. 24 tests, all green.

See the [roadmap](#roadmap) for what each milestone adds and what is explicitly *not built yet*.

## See it work

```bash
python scripts/demo.py
```

A deploy silently renames `"UK"` → `"United Kingdom"`. Every structural check stays green; DVI still catches it, attributes it, and scopes the blast radius:

```text
  Structural checks: schema OK | row_count OK | freshness OK | nulls OK

  DATA INCIDENT
  Severity    : HIGH
  Change at   : 09:14
  Detected at : 09:16

  Suspected data incident from change 'deploy #482 (country normalization)'.
  Value 'UK' (20.0% of the distribution) appears replaced by 'United Kingdom'
  (20.0%) on model.shop.fact_orders; 3 downstream asset(s) affected.

  Affected downstream assets:
    - model.shop.exec_dashboard
    - model.shop.ml_ltv_feature
    - model.shop.revenue_daily

  Evidence:
    * Change 'deploy #482 ...' was deployed 2 min before the first symptom.
    * 'deploy #482 ...' directly changed model.shop.fact_orders, where DVI
      observed: Value 'UK' (20.0%) appears replaced by 'United Kingdom' (20.0%).
    * No corresponding change was observed upstream of the targeted asset(s).
```

Note what DVI does **not** do: it prints no fabricated "92% confidence". It shows the ranked cause and the observable evidence. Calibrated, *measured* confidence arrives in M3.

## Roadmap

DVI is built as a **walking skeleton** — the riskiest, most novel part (does semantic detection + causal ranking actually work?) is proven first; UI and connectors come last.

| Milestone | Adds | Proves |
|-----------|------|--------|
| **M1** ✅ | Value-substitution signature end-to-end on synthetic data | The core hypothesis is alive |
| **M2** | Signatures 2–5 + negatives/decoys/concurrency benchmark | Recall at a fixed false-positive budget |
| **M3** | Calibrated logistic confidence + reliability diagram | Honest, *measured* confidence |
| **M4** | Blast-radius + external-asset lineage (dashboards/ML/APIs) | Business-level impact |
| **M5** | Snowflake pushdown profiling + CLI / GitHub Action PR reports | Real-user adoption path |
| **M6** | Production-grade web UI + incident timeline | Operator experience |

Commodity signatures (null-explosion, cardinality, volume, duplicate-rate, schema/type) are slotted in where cheap.

### Explicitly not built yet
- Automatic BI/ML lineage discovery (Tableau/Looker/feature stores) — downstream assets register via dbt exposures / a generic API until then.
- Warehouses other than Snowflake (DuckDB/Postgres work via the local profiling path).
- Any autonomous remediation.

## Getting started

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash);  use source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
pytest
```

## License

MIT — see [LICENSE](LICENSE).
