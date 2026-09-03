"""Behavioral tests for the incident store (issue #9).

The store persists incidents across runs with a stable identity so recurring
incidents dedupe (upsert) instead of duplicating, and history for an asset is
queryable over time. Everything is deterministic: timestamps are supplied, never
read from the wall clock.
"""

from datetime import UTC, datetime, timedelta

from dvi.detection import Symptom
from dvi.incidents import Incident
from dvi.rca import ChangeEvent, Observation, RootCauseCandidate
from dvi.store import IncidentRecord, SqliteIncidentStore, incident_identity

_T0 = datetime(2026, 8, 25, 9, 14, tzinfo=UTC)


def _incident(
    *,
    change_id="pr-1",
    signature="value_substitution",
    column="country",
    severity="high",
    magnitude=0.4,
    label="rename country codes",
    detected_at=_T0,
):
    symptom = Symptom(signature=signature, column=column, magnitude=magnitude,
                      confidence=0.94)
    change = ChangeEvent(id=change_id, timestamp=_T0, targets=["model.shop.stg_orders"],
                         label=label)
    obs = Observation(asset="model.shop.fct_orders", observed_at=detected_at,
                      symptom=symptom)
    cause = RootCauseCandidate(change=change, score=1.0, explained=[obs],
                               evidence=["country: UK -> GB"])
    return Incident(
        title=f"Semantic change in {column} - {label}",
        severity=severity,
        summary="Suspected data incident.",
        primary_cause=cause,
        affected_assets={"model.shop.rpt_orders"},
        evidence=["country: UK -> GB"],
        detected_at=detected_at,
        change_at=_T0,
        confidence=0.94,
    )


def _store(tmp_path):
    return SqliteIncidentStore(tmp_path / "incidents.db")


def test_identity_is_stable_across_equal_incidents():
    a = incident_identity("model.shop.fct_orders", _incident())
    b = incident_identity("model.shop.fct_orders", _incident())
    assert a == b


def test_identity_differs_by_asset_signature_and_change():
    base = incident_identity("model.shop.fct_orders", _incident())
    assert base != incident_identity("model.shop.other", _incident())
    assert base != incident_identity(
        "model.shop.fct_orders", _incident(signature="distribution_shift")
    )
    assert base != incident_identity(
        "model.shop.fct_orders", _incident(change_id="pr-2")
    )


def test_record_persists_a_queryable_row(tmp_path):
    store = _store(tmp_path)
    rec = store.record(_incident(), asset="model.shop.fct_orders", run_at=_T0)

    assert isinstance(rec, IncidentRecord)
    assert rec.asset == "model.shop.fct_orders"
    assert rec.signature == "value_substitution"
    assert rec.column == "country"
    assert rec.change_id == "pr-1"
    assert rec.severity == "high"
    assert rec.confidence == 0.94
    assert rec.occurrences == 1
    assert rec.first_seen_at == _T0
    assert rec.last_seen_at == _T0


def test_record_survives_a_reopen(tmp_path):
    store = _store(tmp_path)
    store.record(_incident(), asset="model.shop.fct_orders", run_at=_T0)
    store.close()

    reopened = _store(tmp_path)
    rows = reopened.history("model.shop.fct_orders")
    assert len(rows) == 1
    assert rows[0].change_id == "pr-1"


def test_recurring_incident_upserts_and_counts_occurrences(tmp_path):
    store = _store(tmp_path)
    later = _T0 + timedelta(days=1)

    store.record(_incident(), asset="model.shop.fct_orders", run_at=_T0)
    rec = store.record(_incident(), asset="model.shop.fct_orders", run_at=later)

    assert rec.occurrences == 2
    assert rec.first_seen_at == _T0       # first_seen is stable
    assert rec.last_seen_at == later      # last_seen advances
    assert len(store.history("model.shop.fct_orders")) == 1  # deduped, not duplicated


def test_distinct_incidents_are_separate_rows(tmp_path):
    store = _store(tmp_path)
    store.record(_incident(change_id="pr-1"), asset="a", run_at=_T0)
    store.record(_incident(change_id="pr-2"), asset="a", run_at=_T0)

    assert len(store.history("a")) == 2


def test_history_is_scoped_to_asset_and_ordered_over_time(tmp_path):
    store = _store(tmp_path)
    store.record(_incident(change_id="pr-late", detected_at=_T0 + timedelta(days=2)),
                 asset="a", run_at=_T0 + timedelta(days=2))
    store.record(_incident(change_id="pr-early", detected_at=_T0),
                 asset="a", run_at=_T0)
    store.record(_incident(change_id="pr-x"), asset="b", run_at=_T0)

    hist = store.history("a")
    assert [r.change_id for r in hist] == ["pr-late", "pr-early"]  # newest first
    assert all(r.asset == "a" for r in hist)


def test_get_returns_record_by_identity(tmp_path):
    store = _store(tmp_path)
    key = incident_identity("model.shop.fct_orders", _incident())
    assert store.get(key) is None
    store.record(_incident(), asset="model.shop.fct_orders", run_at=_T0)
    assert store.get(key).change_id == "pr-1"


def test_prune_drops_records_last_seen_before_cutoff(tmp_path):
    store = _store(tmp_path)
    store.record(_incident(change_id="old", detected_at=_T0), asset="a", run_at=_T0)
    store.record(_incident(change_id="new", detected_at=_T0 + timedelta(days=10)),
                 asset="a", run_at=_T0 + timedelta(days=10))

    deleted = store.prune(before=_T0 + timedelta(days=5))

    assert deleted == 1
    assert [r.change_id for r in store.history("a")] == ["new"]
