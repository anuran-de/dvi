"""Pure core: turn commit records into candidate ChangeEvents.

No git, no I/O. Given commits and a file->nodes resolver, emit one ChangeEvent
per commit that touches at least one modeled asset, dropping the rest.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from dvi.rca import ChangeEvent

from .records import CommitRecord


def derive_change_events(
    commits: Iterable[CommitRecord],
    resolve_targets: Callable[[str], set[str]],
    *,
    sha_length: int = 7,
) -> list[ChangeEvent]:
    events: list[ChangeEvent] = []
    for commit in commits:
        targets: set[str] = set()
        for path in commit.changed_files:
            targets |= resolve_targets(path)
        if not targets:
            continue  # commit touches nothing modeled -> not a candidate
        events.append(
            ChangeEvent(
                id=commit.sha[:sha_length],
                timestamp=commit.timestamp,
                targets=sorted(targets),
                label=commit.subject,
            )
        )
    # Explicit sort so ordering never depends on set/dict iteration.
    return sorted(events, key=lambda e: (e.timestamp, e.id))
