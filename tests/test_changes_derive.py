from datetime import datetime

from dvi.changes import CommitRecord, derive_change_events


def _resolver(mapping):
    return lambda path: set(mapping.get(path, set()))


def test_maps_changed_files_to_targets_one_event_per_commit():
    commits = [
        CommitRecord(
            sha="abcdef1234567890",
            timestamp=datetime(2026, 8, 25, 9, 50),
            subject="deploy stg_orders",
            changed_files=("models/stg_orders.sql",),
        ),
    ]
    resolve = _resolver({"models/stg_orders.sql": {"model.shop.stg_orders"}})

    events = derive_change_events(commits, resolve)

    assert len(events) == 1
    ev = events[0]
    assert ev.id == "abcdef1"                      # short sha, 7 chars
    assert ev.timestamp == datetime(2026, 8, 25, 9, 50)
    assert ev.targets == ["model.shop.stg_orders"]
    assert ev.label == "deploy stg_orders"


def test_drops_commits_with_no_mapped_targets():
    commits = [
        CommitRecord("a" * 40, datetime(2026, 8, 25, 9, 50), "touch readme",
                     ("README.md",)),
    ]
    events = derive_change_events(commits, _resolver({}))
    assert events == []


def test_unions_targets_across_changed_files_and_sorts_them():
    commits = [
        CommitRecord("beef" + "0" * 36, datetime(2026, 8, 25, 9, 50), "two models",
                     ("models/b.sql", "models/a.sql")),
    ]
    resolve = _resolver({
        "models/a.sql": {"model.shop.a"},
        "models/b.sql": {"model.shop.b"},
    })
    events = derive_change_events(commits, resolve)
    assert events[0].targets == ["model.shop.a", "model.shop.b"]  # sorted


def test_events_sorted_by_timestamp_then_id():
    commits = [
        CommitRecord("f" * 40, datetime(2026, 8, 25, 10, 0), "late", ("models/x.sql",)),
        CommitRecord("0" * 40, datetime(2026, 8, 25, 9, 0), "early", ("models/x.sql",)),
    ]
    resolve = _resolver({"models/x.sql": {"model.shop.x"}})
    events = derive_change_events(commits, resolve)
    assert [e.label for e in events] == ["early", "late"]
