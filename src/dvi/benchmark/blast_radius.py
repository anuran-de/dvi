"""Labeled blast-radius cases: does DVI name the right external consumers, and
does a business-critical consumer lift severity — without false alarms?

Each case is a hand-built lineage with a changed data asset, the ground-truth
set of affected exposures, and the expected incident severity. Decoys must NOT
appear in the affected set or escalate severity:

  * ``sibling_decoy`` — an exposure fed by a *sibling* table, off the blast path;
  * ``ancestor_decoy`` — an exposure on an *upstream* asset, not downstream;
  * ``notebook_no_escalation`` — a LOW notebook is affected but must not escalate.

Positives exercise each escalation path: a high-maturity dashboard (-> high), a
customer-facing application at high maturity (-> critical), and an explicit
``meta.criticality: critical`` override on an otherwise-medium exposure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dvi.detection import Symptom
from dvi.incidents import synthesize_incident
from dvi.lineage import LineageGraph, load_dbt_manifest
from dvi.rca import ChangeEvent, Observation, RootCauseCandidate


@dataclass(frozen=True)
class BlastRadiusCase:
    name: str
    lineage: LineageGraph
    changed: str
    expected_exposures: set[str]
    expected_severity: str
    note: str = ""


@dataclass(frozen=True)
class BlastRadiusCaseResult:
    case: BlastRadiusCase
    found_exposures: set[str]
    severity: str
    exposures_correct: bool
    severity_correct: bool


@dataclass(frozen=True)
class BlastRadiusReport:
    results: list[BlastRadiusCaseResult]

    @property
    def precision(self) -> float:
        tp = fp = 0
        for r in self.results:
            tp += len(r.found_exposures & r.case.expected_exposures)
            fp += len(r.found_exposures - r.case.expected_exposures)
        denom = tp + fp
        return tp / denom if denom else 1.0

    @property
    def recall(self) -> float:
        tp = fn = 0
        for r in self.results:
            tp += len(r.found_exposures & r.case.expected_exposures)
            fn += len(r.case.expected_exposures - r.found_exposures)
        denom = tp + fn
        return tp / denom if denom else 1.0

    @property
    def severity_accuracy(self) -> float:
        if not self.results:
            return 1.0
        return sum(r.severity_correct for r in self.results) / len(self.results)

    @property
    def wrong(self) -> list[str]:
        return [
            r.case.name
            for r in self.results
            if not (r.exposures_correct and r.severity_correct)
        ]


def _exposure(uid, name, type_, maturity, deps, meta=None):
    return {
        uid: {
            "name": name, "type": type_, "maturity": maturity,
            "owner": {"name": "owner"}, "meta": meta or {},
            "depends_on": {"nodes": list(deps)},
        }
    }


def _model(uid, deps=()):
    return {uid: {"resource_type": "model", "depends_on": {"nodes": list(deps)}}}


def build_blast_radius_cases() -> list[BlastRadiusCase]:
    cases: list[BlastRadiusCase] = []

    # 1. High-maturity dashboard downstream -> severity high.
    nodes = {**_model("m.fact"), **_model("m.rev", ["m.fact"])}
    exp = _exposure("e.dash", "exec_dashboard", "dashboard", "high", ["m.rev"])
    cases.append(
        BlastRadiusCase(
            "dashboard_high", load_dbt_manifest({"nodes": nodes, "exposures": exp}),
            "m.fact", {"e.dash"}, "high",
            note="material change reaching a high-maturity dashboard",
        )
    )

    # 2. Customer-facing application at high maturity -> critical.
    exp = _exposure("e.api", "pricing_api", "application", "high", ["m.rev"])
    cases.append(
        BlastRadiusCase(
            "application_critical", load_dbt_manifest({"nodes": nodes, "exposures": exp}),
            "m.fact", {"e.api"}, "critical",
            note="application at maturity:high escalates to critical",
        )
    )

    # 3. meta.criticality override lifts an otherwise-medium dashboard to critical.
    exp = _exposure(
        "e.ovr", "flagged", "dashboard", "medium", ["m.rev"], meta={"criticality": "critical"}
    )
    cases.append(
        BlastRadiusCase(
            "override_critical", load_dbt_manifest({"nodes": nodes, "exposures": exp}),
            "m.fact", {"e.ovr"}, "critical",
            note="explicit meta override wins over derivation",
        )
    )

    # 4. Sibling decoy: exposure fed by a sibling of the changed asset, not downstream.
    nodes4 = {
        **_model("m.root"), **_model("m.a", ["m.root"]), **_model("m.b", ["m.root"]),
    }
    exp4 = _exposure("e.sib", "sibling_dash", "dashboard", "high", ["m.b"])
    cases.append(
        BlastRadiusCase(
            "sibling_decoy", load_dbt_manifest({"nodes": nodes4, "exposures": exp4}),
            "m.a", set(), "medium",
            note="exposure on a sibling branch must not appear or escalate",
        )
    )

    # 5. Ancestor decoy: exposure attached upstream of the change, not reachable downstream.
    nodes5 = {**_model("m.up"), **_model("m.mid", ["m.up"]), **_model("m.down", ["m.mid"])}
    exp5 = _exposure("e.anc", "up_dash", "dashboard", "high", ["m.up"])
    cases.append(
        BlastRadiusCase(
            "ancestor_decoy", load_dbt_manifest({"nodes": nodes5, "exposures": exp5}),
            "m.mid", set(), "high",
            note="upstream exposure is not in the downstream blast radius",
        )
    )

    # 6. Notebook is affected but LOW -> must not escalate above the base severity.
    exp6 = _exposure("e.nb", "scratch", "notebook", "high", ["m.rev"])
    cases.append(
        BlastRadiusCase(
            "notebook_no_escalation", load_dbt_manifest({"nodes": nodes, "exposures": exp6}),
            "m.fact", {"e.nb"}, "high",
            note="LOW notebook is named but severity stays at the base (propagates=high)",
        )
    )

    return cases


def _symptom() -> Symptom:
    return Symptom(
        signature="value_substitution", column="country", magnitude=0.4,
        from_value="UK", to_value="United Kingdom", description="UK -> United Kingdom",
    )


def _incident_for(case: BlastRadiusCase):
    # Symptom lands on the nearest downstream data asset (or the changed asset when
    # it has no downstream data), so the change corroborates it.
    data_down = sorted(case.lineage.data_downstream_of({case.changed}))
    asset = data_down[0] if data_down else case.changed
    obs = Observation(asset, datetime(2026, 8, 25, 10, 0), _symptom())
    change = ChangeEvent("deploy", datetime(2026, 8, 25, 9, 50), [case.changed], "deploy")
    candidate = RootCauseCandidate(change=change, score=1.0, explained=[obs], evidence=["e"])
    return synthesize_incident([candidate], case.lineage, [])


def evaluate_blast_radius(cases: list[BlastRadiusCase] | None = None) -> BlastRadiusReport:
    if cases is None:
        cases = build_blast_radius_cases()
    results: list[BlastRadiusCaseResult] = []
    for case in cases:
        incident = _incident_for(case)
        impact = incident.business_impact
        found = {e.unique_id for e in impact.exposures} if impact else set()
        exposures_correct = found == case.expected_exposures
        severity_correct = incident.severity == case.expected_severity
        results.append(
            BlastRadiusCaseResult(
                case, found, incident.severity, exposures_correct, severity_correct
            )
        )
    return BlastRadiusReport(results)
