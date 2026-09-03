"""The only side-effecting piece: read commits from git via subprocess.

Best-effort by contract — any git problem (not a repo, unknown ref, git not on
PATH) yields an empty list so derivation simply contributes nothing rather than
failing the run. Commit timestamps are normalized to naive UTC to match the
rest of the codebase.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .records import CommitRecord

# Unit separators unlikely to appear in a commit subject.
_FIELD = "\x1f"
_RECORD = "\x1e"
_FORMAT = f"{_RECORD}%H{_FIELD}%cI{_FIELD}%s"


def _to_naive_utc(iso: str) -> datetime:
    ts = datetime.fromisoformat(iso)
    if ts.tzinfo is not None:
        ts = ts.astimezone(UTC).replace(tzinfo=None)
    return ts


def _parse(out: str) -> list[CommitRecord]:
    records: list[CommitRecord] = []
    for chunk in out.split(_RECORD):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        header, _, rest = chunk.partition("\n")
        sha, iso, subject = header.split(_FIELD, 2)
        files = tuple(line for line in rest.splitlines() if line.strip())
        records.append(
            CommitRecord(
                sha=sha,
                timestamp=_to_naive_utc(iso),
                subject=subject,
                changed_files=files,
            )
        )
    return records


def collect_commits(base: str | None, head: str, cwd: Path) -> list[CommitRecord]:
    rng = f"{base}..{head}" if base else head
    try:
        result = subprocess.run(
            ["git", "log", rng, f"--format={_FORMAT}", "--name-only"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return _parse(result.stdout)
