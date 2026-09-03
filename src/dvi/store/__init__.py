"""Incident persistence: a stable-identity store with queryable history."""

from .base import IncidentRecord, IncidentStore, incident_identity
from .sqlite import SqliteIncidentStore

__all__ = [
    "IncidentRecord",
    "IncidentStore",
    "SqliteIncidentStore",
    "incident_identity",
]
