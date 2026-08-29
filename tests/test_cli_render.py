from datetime import UTC, datetime

from dvi.cli.render import render_json, render_markdown
from dvi.incidents import Incident
from dvi.rca import ChangeEvent, RootCauseCandidate


def _incident():
    change = ChangeEvent(
        id="pr-1",
        timestamp=datetime(2026, 8, 30, tzinfo=UTC),
        targets=["model.shop.stg_orders"],
        label="rename country codes",
    )
    return Incident(
        title="Semantic change in country - rename country codes",
        severity="high",
        summary="Suspected data incident from change 'rename country codes'.",
        primary_cause=RootCauseCandidate(change=change, score=1.0),
        affected_assets={"model.shop.fct_orders"},
        evidence=["country: UK -> GB (40 rows)"],
        confidence=0.87,
    )


def test_markdown_incident_has_verdict_and_marker():
    md = render_markdown(_incident(), asset="model.shop.fct_orders",
                         fail_on="high", gate_failed=True)
    assert "High-severity semantic change detected" in md
    assert "country: UK -> GB (40 rows)" in md
    assert "`model.shop.fct_orders`" in md
    assert "87%" in md               # confidence rendered
    assert "FAILED" in md            # gate line
    assert md.rstrip().endswith("<!-- dvi-report -->")


def test_markdown_no_incident_is_green_report():
    md = render_markdown(None, asset="model.shop.fct_orders",
                         fail_on="high", gate_failed=False)
    assert "No semantic change detected" in md
    assert "<!-- dvi-report -->" in md
    assert "FAILED" not in md


def test_json_incident_schema():
    js = render_json(_incident(), asset="model.shop.fct_orders",
                     fail_on="high", gate_failed=True,
                     generated_at=datetime(2026, 8, 30, tzinfo=UTC))
    assert js["asset"] == "model.shop.fct_orders"
    assert js["severity"] == "high"
    assert js["gate"] == {"fail_on": "high", "failed": True}
    assert js["incident"]["title"].startswith("Semantic change in country")
    assert js["incident"]["affected_assets"] == ["model.shop.fct_orders"]
    assert js["incident"]["confidence"] == 0.87
    assert js["generated_at"] == "2026-08-30T00:00:00+00:00"


def test_json_no_incident_is_null():
    js = render_json(None, asset="a", fail_on="high", gate_failed=False,
                     generated_at=datetime(2026, 8, 30, tzinfo=UTC))
    assert js["incident"] is None
    assert js["severity"] is None
    assert js["gate"]["failed"] is False
