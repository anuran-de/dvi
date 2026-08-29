# tests/test_action_yml.py
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_ACTION = _ROOT / "action.yml"
_WORKFLOW = _ROOT / ".github" / "workflows" / "dvi-example.yml"


def test_action_yml_exists_and_is_composite():
    text = _ACTION.read_text(encoding="utf-8")
    assert "name:" in text
    assert "description:" in text
    assert "runs:" in text
    assert "composite" in text


def test_action_declares_and_references_inputs():
    text = _ACTION.read_text(encoding="utf-8")
    for name in ("config", "output-dir"):
        assert f"{name}:" in text            # declared under inputs:
        assert f"inputs.{name}" in text      # referenced in a step


def test_action_runs_cli_and_posts_sticky_comment():
    text = _ACTION.read_text(encoding="utf-8")
    assert "dvi analyze" in text
    assert "<!-- dvi-report -->" in text     # sticky-comment marker
    assert "gh " in text                     # posts via the gh CLI


def test_example_workflow_wires_pull_request():
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request" in text
    assert "pull-requests: write" in text
    assert "uses: ./" in text
