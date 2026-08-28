from datetime import datetime

import polars as pl

from dvi.incidents import Incident
from dvi.lineage import LineageGraph
from dvi.pipeline import (
    analyze_change_from_profiles,
    detect_symptoms,
    detect_symptoms_from_profiles,
)
from dvi.profiling import profile_column
from dvi.rca import ChangeEvent

ASSET = "model.shop.fact_orders"


def _lineage() -> LineageGraph:
    g = LineageGraph()
    g.add_edge(ASSET, "model.shop.revenue_daily")
    return g


def _profiles(df: pl.DataFrame) -> dict:
    return {c: profile_column(df[c].rename(c)) for c in df.columns}


def test_detect_symptoms_from_profiles_matches_dataframe_path():
    before = pl.DataFrame({"country": ["UK"] * 200 + ["US"] * 800})
    after = pl.DataFrame({"country": ["United Kingdom"] * 200 + ["US"] * 800})

    from_df = detect_symptoms(before, after, ["country"])
    from_prof = detect_symptoms_from_profiles(_profiles(before), _profiles(after), ["country"])

    assert [s.signature for s in from_df] == [s.signature for s in from_prof]
    assert [s.column for s in from_df] == [s.column for s in from_prof]
    assert from_prof[0].from_value == "UK"
    assert from_prof[0].to_value == "United Kingdom"


def test_analyze_change_from_profiles_yields_incident():
    before = pl.DataFrame({"country": ["UK"] * 200 + ["US"] * 800})
    after = pl.DataFrame({"country": ["United Kingdom"] * 200 + ["US"] * 800})
    deploy = ChangeEvent("deploy-1", datetime(2026, 8, 25, 9, 0), [ASSET], "deploy")

    incident = analyze_change_from_profiles(
        asset=ASSET,
        before=_profiles(before),
        after=_profiles(after),
        observed_at=datetime(2026, 8, 25, 9, 5),
        lineage=_lineage(),
        changes=[deploy],
        columns=["country"],
    )

    assert isinstance(incident, Incident)
    assert incident.primary_cause.change.id == "deploy-1"


def test_no_symptoms_returns_none():
    same = pl.DataFrame({"country": ["UK"] * 200 + ["US"] * 800})
    incident = analyze_change_from_profiles(
        asset=ASSET,
        before=_profiles(same),
        after=_profiles(same),
        observed_at=datetime(2026, 8, 25, 9, 5),
        lineage=_lineage(),
        changes=[],
        columns=["country"],
    )
    assert incident is None
