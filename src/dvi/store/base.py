"""The incident store contract: a stable identity, a record shape, and an ABC.

Detection is otherwise stateless — each run analyzes one before/after pair. The
store gives incidents a history so recurring ones dedupe (upsert on a stable
identity) and an asset's incidents are queryable over time. Identity and run
timestamps are always supplied by the caller (never read from the wall clock),
so a re-run of the same snapshot maps to the same row and stays deterministic.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from dvi.incidents import Incident
from dvi.rca import Observation


@dataclass(frozen=True)
class IncidentRecord:
    """One persisted incident with its dedupe/history bookkeeping."""

    identity_key: str
    asset: str
    signature: str
    column: str
    change_id: str
    change_label: str
    severity: str
    confidence: float | None
    title: str
    summary: str
    change_at: datetime | None
    first_detected_at: datetime | None
    last_detected_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    occurrences: int


def _worst(incident: Incident) -> Observation:
    """The highest-magnitude observation — the incident's defining symptom."""
    return max(incident.primary_cause.explained, key=lambda o: o.symptom.magnitude)


def incident_identity(asset: str, incident: Incident) -> str:
    """Stable identity = analyzed asset + primary signature + change event.

    Deterministic and collision-resistant (SHA-256), so the same incident from a
    re-run upserts onto one row while a different asset, signature, or change
    event lands on a distinct one.
    """
    worst = _worst(incident)
    change_id = incident.primary_cause.change.id
    raw = f"{asset}\x00{worst.symptom.signature}\x00{change_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class IncidentStore(ABC):
    """Persist incidents and query their history.

    A default local backend ships in :mod:`dvi.store.sqlite`; the interface keeps
    room for a server-backed store (e.g. Postgres) later.
    """

    @abstractmethod
    def record(self, incident: Incident, *, asset: str, run_at: datetime) -> IncidentRecord:
        """Upsert ``incident`` for ``asset`` observed at ``run_at``; return the row."""

    @abstractmethod
    def history(self, asset: str) -> list[IncidentRecord]:
        """All incidents recorded for ``asset``, newest detection first."""

    @abstractmethod
    def get(self, identity_key: str) -> IncidentRecord | None:
        """The record with this identity, or ``None``."""

    @abstractmethod
    def prune(self, *, before: datetime) -> int:
        """Delete records last seen before ``before``; return how many were removed."""

    @abstractmethod
    def close(self) -> None:
        """Release the backend's resources."""

    def __enter__(self) -> IncidentStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
