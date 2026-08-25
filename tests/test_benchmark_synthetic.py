from dvi.benchmark import inject_value_substitution, make_orders


def test_make_orders_has_requested_uk_share():
    df = make_orders(n=1000, uk_share=0.2, seed=7)
    assert df.height == 1000
    uk = df.filter(df["country"] == "UK").height
    assert uk == 200


def test_inject_value_substitution_relabels_all_matching_values():
    df = make_orders(n=1000, uk_share=0.2, seed=7)

    mutated = inject_value_substitution(df, "country", "UK", "United Kingdom")

    assert mutated.filter(mutated["country"] == "UK").height == 0
    assert mutated.filter(mutated["country"] == "United Kingdom").height == 200
    # nothing else moved: total row count preserved
    assert mutated.height == df.height
