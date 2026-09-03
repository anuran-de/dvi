"""A commit as far as change-derivation cares: id, time, subject, files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CommitRecord:
    sha: str
    timestamp: datetime
    subject: str
    changed_files: tuple[str, ...]
