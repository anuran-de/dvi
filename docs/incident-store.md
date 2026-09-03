# Incident store — history across runs

By default DVI is **stateless**: each `dvi analyze` run compares one before/after
snapshot pair and writes a fresh report. Nothing remembers what fired last week.

The **incident store** adds an optional, opt-in history layer. When a `[store]`
section is present in `dvi.toml`, every run that produces an incident records it,
so you can answer:

- *Has this incident fired before?* (a stable identity dedupes recurrences)
- *How has this asset trended over time?* (`history(asset)`)
- *Which incidents are stale enough to drop?* (`prune`)

It is deliberately small and dependency-free — a local SQLite file (Python stdlib
`sqlite3`) — with an `IncidentStore` interface that leaves room for a
server-backed store (e.g. Postgres) later.

## Enabling it

```toml
# dvi.toml
[store]
path = ".dvi/incidents.db"   # created (with parent dirs) on first run
```

With no `[store]` section, behavior is unchanged and no database is written.
Recording never changes the CLI exit code (0 clean / 1 gate tripped / 2 could-not-run);
a store write failure surfaces as exit 2 with a clear message, like any other
could-not-run error.

## Stable identity (dedupe)

Each incident gets a deterministic identity:

```
identity = SHA-256( asset ⊕ primary_signature ⊕ change_event_id )
```

- **asset** — the analyzed asset from the config.
- **primary_signature** — the signature of the incident's highest-magnitude symptom.
- **change_event_id** — the `[[changes]]` entry RCA attributed the incident to.

Re-running the *same* snapshot re-derives the *same* identity, so the store
**upserts** onto one row rather than piling up duplicates: `occurrences` bumps,
`last_seen_at` / `last_detected_at` advance, and `first_seen_at` /
`first_detected_at` stay put. A different asset, signature, or change event is a
distinct row.

## Determinism

The recorded run timestamp is the incident's `detected_at`, which DVI anchors to
the declared change timestamps — **not** the wall clock. Two runs of the same
inputs therefore produce byte-identical records, which keeps CI and tests stable.

## Query API

```python
from datetime import datetime, timezone
from dvi.store import SqliteIncidentStore

with SqliteIncidentStore(".dvi/incidents.db") as store:
    for rec in store.history("model.shop.fct_orders"):   # newest detection first
        print(rec.change_id, rec.severity, rec.occurrences, rec.last_detected_at)

    one = store.get(identity_key)          # a single record, or None

    dropped = store.prune(                  # retention: delete stale records
        before=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
```

An `IncidentRecord` carries the identity, the asset/signature/column, the change
event, the severity/confidence/title/summary snapshot, and the
first/last-seen and first/last-detected timestamps plus the occurrence count.

## Retention

The store does not expire rows on its own — history is kept until you prune it.
Call `prune(before=<cutoff>)` (e.g. from a scheduled job) to drop incidents whose
`last_seen_at` predates the cutoff. Because the backend is a single SQLite file,
retention can also be as simple as rotating or deleting that file.

## Roadmap

The store is the persistence seam the operator UI and org-scale features build on:
feeding real history into the UI (replacing static fixtures) and per-tenant
scoping for access control are tracked as separate issues.
