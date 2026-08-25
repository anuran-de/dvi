from datetime import datetime, timedelta

from dvi.detection import Symptom
from dvi.lineage import LineageGraph
from dvi.rca import ChangeEvent, Observation, RootCauseCandidate, rank_root_causes


def _lineage() -> LineageGraph:
    g = LineageGraph()
    g.add_edge("model.shop.fact_orders", "model.shop.revenue_daily")
    return g


def _symptom(column: str = "country") -> Symptom:
    return Symptom(
        signature="value_substitution",
        column=column,
        magnitude=0.2,
        from_value="UK",
        to_value="United Kingdom",
    )


def _observations() -> list[Observation]:
    return [
        Observation("model.shop.fact_orders", datetime(2026, 8, 25, 9, 16), _symptom()),
        Observation(
            "model.shop.revenue_daily",
            datetime(2026, 8, 25, 9, 17),
            _symptom("revenue"),
        ),
    ]


def test_ranks_upstream_prior_change_first():
    changes = [
        ChangeEvent("c1", datetime(2026, 8, 25, 9, 14), ["model.shop.fact_orders"], "deploy #482"),
        ChangeEvent("c2", datetime(2026, 8, 25, 9, 14), ["model.shop.inventory"], "deploy #483"),
        ChangeEvent("c3", datetime(2026, 8, 25, 9, 20), ["model.shop.fact_orders"], "deploy #484"),
    ]

    ranked = rank_root_causes(_observations(), changes, _lineage())

    assert [c.change.id for c in ranked] == ["c1"]
    assert isinstance(ranked[0], RootCauseCandidate)


def test_change_after_anomaly_is_not_a_candidate():
    changes = [
        ChangeEvent("late", datetime(2026, 8, 25, 9, 20), ["model.shop.fact_orders"], "deploy")
    ]
    assert rank_root_causes(_observations(), changes, _lineage()) == []


def test_unrelated_change_does_not_explain_symptoms():
    changes = [
        ChangeEvent("elsewhere", datetime(2026, 8, 25, 9, 10), ["model.shop.inventory"], "deploy")
    ]
    assert rank_root_causes(_observations(), changes, _lineage()) == []


def test_stale_change_outside_window_is_excluded():
    changes = [
        ChangeEvent(
            "old",
            datetime(2026, 8, 25, 9, 16) - timedelta(days=3),
            ["model.shop.fact_orders"],
            "deploy",
        )
    ]
    assert rank_root_causes(_observations(), changes, _lineage()) == []


def test_top_candidate_carries_evidence_and_explained_observations():
    changes = [
        ChangeEvent("c1", datetime(2026, 8, 25, 9, 14), ["model.shop.fact_orders"], "deploy #482")
    ]

    top = rank_root_causes(_observations(), changes, _lineage())[0]

    assert len(top.explained) == 2  # explains both the direct and downstream symptom
    joined = " ".join(top.evidence).lower()
    assert "deploy #482" in joined
    assert "before" in joined  # temporal precedence stated
