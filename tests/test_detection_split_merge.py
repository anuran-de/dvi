from dvi.detection import Symptom, detect_category_split_merge
from dvi.profiling import ColumnProfile, NumericStats


def _cat(name: str, top_k: dict[str, int]) -> ColumnProfile:
    total = sum(top_k.values())
    return ColumnProfile(
        name=name,
        row_count=total,
        null_count=0,
        distinct_count=len(top_k),
        top_k=dict(top_k),
    )


def test_detects_a_category_split():
    baseline = _cat("category", {"Electronics": 500, "Books": 300, "Toys": 200})
    current = _cat(
        "category",
        {"Consumer Electronics": 300, "Home Electronics": 200, "Books": 300, "Toys": 200},
    )

    symptom = detect_category_split_merge(baseline, current)

    assert isinstance(symptom, Symptom)
    assert symptom.signature == "category_split_merge"
    assert symptom.evidence["kind"] == "split"
    assert symptom.from_value == "Electronics"
    assert set(symptom.evidence["targets"]) == {"Consumer Electronics", "Home Electronics"}
    assert abs(symptom.magnitude - 0.5) < 1e-6


def test_detects_a_category_merge():
    baseline = _cat(
        "category",
        {"Consumer Electronics": 300, "Home Electronics": 200, "Books": 300, "Toys": 200},
    )
    current = _cat("category", {"Electronics": 500, "Books": 300, "Toys": 200})

    symptom = detect_category_split_merge(baseline, current)

    assert symptom is not None
    assert symptom.evidence["kind"] == "merge"
    assert symptom.to_value == "Electronics"
    assert set(symptom.evidence["sources"]) == {"Consumer Electronics", "Home Electronics"}


def test_one_to_one_substitution_is_not_a_split_merge():
    baseline = _cat("country", {"US": 620, "UK": 200, "DE": 180})
    current = _cat("country", {"US": 620, "United Kingdom": 198, "DE": 182})

    assert detect_category_split_merge(baseline, current) is None


def test_stable_categories_do_not_fire():
    top_k = {"Electronics": 500, "Books": 300, "Toys": 200}
    stable = detect_category_split_merge(_cat("c", top_k), _cat("c", dict(top_k)))
    assert stable is None


def test_returns_none_for_numeric_column():
    prof = ColumnProfile(
        name="amount",
        row_count=3,
        null_count=0,
        distinct_count=3,
        numeric=NumericStats(count=3, mean=2, stddev=1, minimum=1, maximum=3),
    )
    assert detect_category_split_merge(prof, prof) is None
