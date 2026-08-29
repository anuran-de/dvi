"""Render an Incident (or its absence) into a Markdown PR comment and JSON.

Both artifacts come from the same Incident, so the human and machine views can
never disagree. The Markdown always ends with an HTML marker so the GitHub
Action can find and update the same sticky comment on each run.
"""

from __future__ import annotations

from datetime import datetime

from dvi.incidents import Incident, render_business_impact

MARKER = "<!-- dvi-report -->"
_EMOJI = {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "🔴"}


def render_markdown(
    incident: Incident | None,
    *,
    asset: str,
    fail_on: str,
    gate_failed: bool,
) -> str:
    lines: list[str] = []
    if incident is None:
        lines.append("✅ **No semantic change detected**")
        lines.append("")
        lines.append(f"Asset: `{asset}`")
    else:
        emoji = _EMOJI.get(incident.severity, "🔴")
        lines.append(
            f"{emoji} **{incident.severity.capitalize()}-severity "
            f"semantic change detected**"
        )
        lines.append("")
        lines.append(f"### {incident.title}")
        lines.append("")
        lines.append(incident.summary)
        if incident.confidence is not None:
            lines.append("")
            lines.append(f"**Confidence:** {incident.confidence:.0%}")
        if incident.evidence:
            lines.append("")
            lines.append("**Evidence:**")
            lines.extend(f"- {e}" for e in incident.evidence)
        if incident.affected_assets:
            rendered = ", ".join(f"`{a}`" for a in sorted(incident.affected_assets))
            lines.append("")
            lines.append(f"**Affected downstream assets:** {rendered}")
        if incident.business_impact is not None:
            lines.append("")
            lines.extend(bl.strip() for bl in render_business_impact(incident.business_impact))
    lines.append("")
    lines.append(f"_Gate: fail_on=`{fail_on}` — {'FAILED' if gate_failed else 'passed'}_")
    lines.append("")
    lines.append(MARKER)
    return "\n".join(lines)


def render_json(
    incident: Incident | None,
    *,
    asset: str,
    fail_on: str,
    gate_failed: bool,
    generated_at: datetime,
) -> dict:
    inc: dict | None = None
    if incident is not None:
        business = None
        if incident.business_impact is not None:
            impact = incident.business_impact
            business = {
                "exposures": [
                    {
                        "name": e.name,
                        "type": e.type,
                        "criticality": e.criticality.name,
                        "owner": e.owner,
                    }
                    for e in impact.exposures
                ],
                "max_criticality": (
                    impact.max_criticality.name if impact.max_criticality else None
                ),
            }
        inc = {
            "title": incident.title,
            "severity": incident.severity,
            "summary": incident.summary,
            "confidence": incident.confidence,
            "affected_assets": sorted(incident.affected_assets),
            "evidence": list(incident.evidence),
            "business_impact": business,
        }
    return {
        "asset": asset,
        "severity": incident.severity if incident else None,
        "incident": inc,
        "gate": {"fail_on": fail_on, "failed": gate_failed},
        "generated_at": generated_at.isoformat(),
    }
