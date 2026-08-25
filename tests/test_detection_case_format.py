from dvi.detection import Symptom, detect_case_format_normalization
from dvi.profiling import ColumnProfile


def _cat(name: str, top_k: dict[str, int]) -> ColumnProfile:
    total = sum(top_k.values())
    return ColumnProfile(
        name=name,
        row_count=total,
        null_count=0,
        distinct_count=len(top_k),
        top_k=dict(top_k),
    )


def test_detects_lowercasing_of_all_categories():
    baseline = _cat("country", {"US": 600, "UK": 200, "DE": 200})
    current = _cat("country", {"us": 600, "uk": 200, "de": 200})

    symptom = detect_case_format_normalization(baseline, current)

    assert isinstance(symptom, Symptom)
    assert symptom.signature == "case_format_normalization"
    # Every category was re-cased, so essentially all mass moved spelling.
    assert symptom.magnitude == 1.0


def test_detects_trailing_whitespace_on_one_category():
    baseline = _cat("status", {"active": 700, "inactive": 300})
    current = _cat("status", {"active ": 700, "inactive": 300})

    symptom = detect_case_format_normalization(baseline, current)

    assert symptom is not None
    assert symptom.from_value == "active"
    assert symptom.to_value == "active "
    assert abs(symptom.magnitude - 0.7) < 1e-6


def test_genuine_substitution_is_not_a_case_format_change():
    # "UK" -> "United Kingdom": different even after casefolding, so #2 must abstain.
    baseline = _cat("country", {"US": 620, "UK": 200, "DE": 180})
    current = _cat("country", {"US": 620, "United Kingdom": 198, "DE": 182})

    assert detect_case_format_normalization(baseline, current) is None


def test_stable_categories_do_not_fire():
    top_k = {"US": 600, "UK": 200, "DE": 200}
    stable = detect_case_format_normalization(_cat("country", top_k), _cat("country", dict(top_k)))
    assert stable is None


def test_returns_none_for_numeric_column():
    from dvi.profiling import NumericStats

    prof = ColumnProfile(
        name="amount",
        row_count=3,
        null_count=0,
        distinct_count=3,
        numeric=NumericStats(count=3, mean=2, stddev=1, minimum=1, maximum=3),
    )
    assert detect_case_format_normalization(prof, prof) is None
