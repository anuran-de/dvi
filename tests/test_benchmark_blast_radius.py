# tests/test_benchmark_blast_radius.py
from dvi.benchmark import build_blast_radius_cases, evaluate_blast_radius


def test_suite_has_positives_and_decoys():
    cases = build_blast_radius_cases()
    assert len(cases) >= 5
    names = {c.name for c in cases}
    assert "sibling_decoy" in names
    assert "notebook_no_escalation" in names


def test_blast_radius_is_perfect_on_the_labeled_suite():
    report = evaluate_blast_radius()
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.severity_accuracy == 1.0
    assert report.wrong == []
