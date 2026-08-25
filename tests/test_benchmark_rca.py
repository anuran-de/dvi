from dvi.benchmark import build_rca_cases, evaluate_rca


def test_rca_cases_are_labelled_with_a_true_cause():
    cases = build_rca_cases()
    assert len(cases) >= 4
    for case in cases:
        # The true cause must actually be one of the candidate changes.
        assert case.true_change_id in {c.id for c in case.changes}
        # Every case carries at least one distractor to make top-1 meaningful.
        assert len(case.changes) >= 2


def test_true_cause_ranks_first_under_distractors():
    cases = build_rca_cases()

    report = evaluate_rca(cases)

    assert report.top1_accuracy == 1.0
    assert report.wrong == []
