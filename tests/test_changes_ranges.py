from dvi.changes import resolve_range


def test_default_range_when_nothing_provided():
    assert resolve_range({}) == ("HEAD~1", "HEAD")


def test_github_env_supplies_base_and_head():
    env = {"GITHUB_BASE_REF": "main", "GITHUB_SHA": "deadbeef"}
    assert resolve_range(env) == ("main", "deadbeef")


def test_explicit_args_win_over_env():
    env = {"GITHUB_BASE_REF": "main", "GITHUB_SHA": "deadbeef"}
    assert resolve_range(env, base="v1.0.0", head="v1.1.0") == ("v1.0.0", "v1.1.0")
