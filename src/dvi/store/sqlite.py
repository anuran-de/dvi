"""A local SQLite incident store — the default backend (stdlib only).

One table keyed by the stable incident identity. Recording is an upsert: a
recurring incident bumps ``occurrences`` and advances ``last_seen``/``last_detected``
while ``first_seen``/``first_detected`` stay put, so "has this fired before?" and
"how has this asset trended?" are answerable without duplicating rows.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from dvi.incidents import Incident

from .base import IncidentRecord, IncidentStore, _worst, incident_identity

_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    identity_key      TEXT PRIMARY KEY,
    asset             TEXT NOT NULL,
    signature         TEXT NOT NULL,
    column_name       TEXT NOT NULL,
    change_id         TEXT NOT NULL,
    change_label      TEXT NOT NULL,
    severity          TEXT NOT NULL,
    confidence        REAL,
    title             TEXT NOT NULL,
    summary           TEXT NOT NULL,
    change_at         TEXT,
    first_detected_at TEXT,
    last_detected_at  TEXT,
    first_seen_at     TEXT NOT NULL,
    last_seen_at      TEXT NOT NULL,
    occurrences       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS incidents_by_asset ON incidents (asset);
"""

_COLUMNS = (
    "identity_key", "asset", "signature", "column_name", "change_id", "change_label",
    "severity", "confidence", "title", "summary", "change_at", "first_detected_at",
    "last_detected_at", "first_seen_at", "last_seen_at", "occurrences",
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


class SqliteIncidentStore(IncidentStore):
    """File-backed incident store. Creates the schema on open."""

    def __init__(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(p))
        self._con.row_factory = sqlite3.Row
        self._con.executescript(_SCHEMA)
        self._con.commit()

    def record(self, incident: Incident, *, asset: str, run_at: datetime) -> IncidentRecord:
        key = incident_identity(asset, incident)
        worst = _worst(incident)
        run_iso = _iso(run_at)
        detected_iso = _iso(incident.detected_at)
        # Insert as a fresh sighting; on a repeat identity, keep the first-seen
        # fields, advance the last-seen fields, refresh the mutable snapshot, and
        # bump the occurrence count.
        self._con.execute(
            """
            INSERT INTO incidents (
                identity_key, asset, signature, column_name, change_id, change_label,
                severity, confidence, title, summary, change_at,
                first_detected_at, last_detected_at, first_seen_at, last_seen_at,
                occurrences
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(identity_key) DO UPDATE SET
                severity         = excluded.severity,
                confidence       = excluded.confidence,
                title            = excluded.title,
                summary          = excluded.summary,
                change_at        = excluded.change_at,
                last_detected_at = excluded.last_detected_at,
                last_seen_at     = excluded.last_seen_at,
                occurrences      = incidents.occurrences + 1
            """,
            (
                key, asset, worst.symptom.signature, worst.symptom.column,
                incident.primary_cause.change.id, incident.primary_cause.change.label,
                incident.severity, incident.confidence, incident.title, incident.summary,
                _iso(incident.change_at), detected_iso, detected_iso, run_iso, run_iso,
            ),
        )
        self._con.commit()
        got = self.get(key)
        assert got is not None  # just written
        return got

    def history(self, asset: str) -> list[IncidentRecord]:
        rows = self._con.execute(
            "SELECT * FROM incidents WHERE asset = ? "
            "ORDER BY last_detected_at DESC, identity_key ASC",
            (asset,),
        ).fetchall()
        return [self._row(r) for r in rows]

    def get(self, identity_key: str) -> IncidentRecord | None:
        row = self._con.execute(
            "SELECT * FROM incidents WHERE identity_key = ?", (identity_key,)
        ).fetchone()
        return self._row(row) if row is not None else None

    def prune(self, *, before: datetime) -> int:
        cur = self._con.execute(
            "DELETE FROM incidents WHERE last_seen_at < ?", (_iso(before),)
        )
        self._con.commit()
        return cur.rowcount

    def close(self) -> None:
        self._con.close()

    @staticmethod
    def _row(row: sqlite3.Row) -> IncidentRecord:
        return IncidentRecord(
            identity_key=row["identity_key"],
            asset=row["asset"],
            signature=row["signature"],
            column=row["column_name"],
            change_id=row["change_id"],
            change_label=row["change_label"],
            severity=row["severity"],
            confidence=row["confidence"],
            title=row["title"],
            summary=row["summary"],
            change_at=_dt(row["change_at"]),
            first_detected_at=_dt(row["first_detected_at"]),
            last_detected_at=_dt(row["last_detected_at"]),
            first_seen_at=_dt(row["first_seen_at"]),
            last_seen_at=_dt(row["last_seen_at"]),
            occurrences=row["occurrences"],
        )
