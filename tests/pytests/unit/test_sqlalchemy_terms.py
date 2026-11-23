"""
Check that flattened terms and compiled targets agree with subdict_match.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import salt.utils.data
from salt.sqlalchemy import terms


def _subtree(data, keys):
    return {key: data[key] for key in keys if key in data}


def _hit(flat, exact, prefixes):
    """Whether stored terms contain a term, or one starting with a prefix."""
    return bool(flat & exact) or any(
        entry.startswith(prefix) for entry in flat for prefix in prefixes
    )


def _assert_plan_agrees(
    data, expr, delimiter=":", regex_match=False, exact_match=False
):
    plan = terms.compile_target(expr, delimiter, regex_match, exact_match)
    expected = bool(
        salt.utils.data.subdict_match(
            data,
            expr,
            delimiter=delimiter,
            regex_match=regex_match,
            exact_match=exact_match,
        )
    )
    if plan.fallback:
        return plan
    if plan.never:
        assert not expected
        return plan
    flat = set(terms.flatten(data))
    certain = _hit(flat, plan.certain, plan.certain_prefixes)
    candidate = _hit(flat, plan.candidates, plan.candidate_prefixes)
    if certain:
        assert expected, (data, expr, plan)
    if expected:
        assert certain or candidate, (data, expr, plan)
    if candidate and terms.RECHECK not in flat:
        # Rechecks fetch only the keys subdict_match can read.
        recheck = salt.utils.data.subdict_match(
            _subtree(data, plan.keys),
            expr,
            delimiter=delimiter,
            regex_match=regex_match,
            exact_match=exact_match,
        )
        assert bool(recheck) == expected, (data, expr)
    return plan


def _certain(data, expr, **kwargs):
    plan = _assert_plan_agrees(data, expr, **kwargs)
    flat = set(terms.flatten(data))
    return _hit(flat, plan.certain, plan.certain_prefixes)


@pytest.mark.parametrize(
    "data,expr,kwargs",
    [
        ({"os": "Ubuntu"}, "os:ubuntu", {}),
        ({"roles": ["web", "db"]}, "roles:web", {}),
        ({"bb": {"bbcpu": {"rhsttag": True}}}, "bb:bbcpu:rhsttag", {}),
        ({"bb": {"bbcpu": {"rhsttag": "x"}}}, "bb:bbcpu:rhsttag", {}),
        ({"systemd": {"version": "252"}}, "systemd:version", {}),
        ({"bb": "bbcpu:rhsttag"}, "bb:bbcpu:rhsttag", {}),
        ({"virtual": True}, "virtual:True", {}),
        ({"env": "PROD"}, "env:prod", {"exact_match": True}),
        ({"os": "Ubuntu"}, "os:ubu*", {}),
        ({"os": "Ubuntu"}, "os:ubu", {"regex_match": True}),
        ({"os": "Ubuntu"}, "os:ubu.*", {"regex_match": True}),
        # Prefix searches of any length prove trailing-wildcard globs.
        ({"os": "Ubuntu"}, "os:ubun*", {}),
        ({"os": "CentOS"}, "os:cento*", {}),
        ({"bb": {"cluster": "cluster-017"}}, "bb:cluster:cluster-01*", {}),
        ({"systemd": {"version": "252"}}, "systemd:ver*", {}),
        ({"os": "Ubuntu"}, "os:ubuntu", {"regex_match": True}),
    ],
)
def test_common_targets_are_certain(data, expr, kwargs):
    assert _certain(data, expr, **kwargs)


@pytest.mark.parametrize(
    "data,expr,kwargs",
    [
        ({"role": "web1"}, "role:web?", {}),
        ({"ipv4": ["10.0.0.1", "127.0.0.1"]}, "ipv4:1:127.0.0.1", {}),
        ({"os": "Ubuntu"}, "'os':ubuntu", {}),
        ({"os": "Ubuntu"}, "os:*", {}),
        ({"a": [{"b": "c"}]}, "a:b:c", {}),
        ({"a": [{"b": "c"}]}, "a:b", {}),
        ({"a": [["b"]]}, "a:*b*", {}),
        ({"os": "Ubuntu"}, "os:ubu.+", {"regex_match": True}),
        ({"os": "Ubuntu"}, "os:(ubu|deb).*", {"regex_match": True}),
        ({"os": "ubntu"}, "os:ubu?ntu", {"regex_match": True}),
        # Floats can read back differently from JSONB.
        ({"osrelease": 22.04}, "osrelease:22.04", {}),
    ],
)
def test_other_targets_are_rechecked(data, expr, kwargs):
    assert not _certain(data, expr, **kwargs)
    assert salt.utils.data.subdict_match(data, expr, **kwargs)


@pytest.mark.parametrize(
    "expr,kwargs,reason",
    [
        ("*:os:ubuntu", {}, "wildcard-root"),
        ("os:*:ubuntu", {}, "wildcard-segment"),
        ("os*ubuntu", {"delimiter": "*"}, "wildcard-delimiter"),
        (["os", "ubuntu"], {}, "unsupported-arguments"),
    ],
)
def test_fallbacks(expr, kwargs, reason):
    assert terms.compile_target(expr, **kwargs).fallback == reason


def test_readings_are_not_repeated():
    out = []
    terms._readings((), ":".join(f"t{i}" for i in range(7)), ":", out)
    assert len(out) == len(set(out)) == 6
    # Deep targets no longer exhaust the reading limit through duplicates.
    assert terms.compile_target(":".join(f"t{i}" for i in range(8))).fallback is None


def test_no_delimiter_never_matches():
    assert terms.compile_target("os").never


@pytest.mark.parametrize(
    "value,expr",
    [
        # JSONB stores -0.0 as 0.0 and 1e+20 as an integer.
        (-0.0, "a:0.0"),
        (1e20, "a:100000000000000000000"),
        (22.04, "a:22.04"),
        ({"x", "y"}, "a:*x*"),
    ],
)
def test_values_storage_may_change_are_rechecked(value, expr):
    flat = set(terms.flatten({"a": value}))
    assert terms.term(terms.UNCERTAIN, ("a",)) in flat
    assert not any(entry.startswith(terms.VALUE) for entry in flat)
    plan = terms.compile_target(expr)
    assert terms.term(terms.UNCERTAIN, ("a",)) in plan.candidates


@pytest.mark.parametrize("expr", ["'os':ubuntu", "'os':ubu*", "'os':ubu.*"])
def test_yaml_normalized_paths_are_never_certain(expr):
    # Traversal only falls back to the YAML-normalized key when the literal
    # key is missing; here the literal key exists and does not match.
    data = {"'os'": "debian", "os": "ubuntu"}
    kwargs = {"regex_match": True} if expr.endswith(".*") else {}
    assert not salt.utils.data.subdict_match(data, expr, **kwargs)
    assert not _certain(data, expr, **kwargs)


def test_digested_values_are_rechecked_by_globs():
    data = {"motd": "welcome " * 40}
    flat = set(terms.flatten(data))
    assert terms.term(terms.LONG, ("motd",)) in flat
    plan = terms.compile_target("motd:welcome*")
    assert terms.term(terms.LONG, ("motd",)) in plan.candidates
    assert not _certain(data, "motd:welcome*")
    assert salt.utils.data.subdict_match(data, "motd:welcome*")


def test_oversized_documents_are_always_rechecked():
    # 48 KB of JSON whose terms pass the tsvector size limit.
    data = {"a" * 90: {"b" * 70: {f"k{i:05}": "x" for i in range(3200)}}}
    assert terms.flatten(data) == [terms.RECHECK]
    expr = ":".join(("a" * 90, "b" * 70, "k03000", "x"))
    assert salt.utils.data.subdict_match(data, expr)
    _assert_plan_agrees(data, expr)
    assert not _certain(data, expr)


def test_long_terms_are_digested():
    flat = terms.flatten({"motd": "x" * 500})
    assert any(entry.startswith("h") and len(entry) == 65 for entry in flat)
    assert _certain({"motd": "x" * 500}, "motd:" + "x" * 500)


KEYS = st.sampled_from(
    ["os", "OS", "roles", "a", "b", "eth0", "10", "1", "0", "x:y", "Ü", "'q'", "ubu"]
)
SCALARS = st.one_of(
    st.sampled_from(
        ["ubuntu", "Ubuntu", "ubu", "web", "WEB1", "10.0.0.5", "fe80::1", "a:b", ""]
    ),
    st.sampled_from(["ünï", "*", "web*", "x" * 300]),
    st.integers(-3, 30),
    st.booleans(),
    st.none(),
    st.sampled_from([0.5, 1.0, 22.04]),
)
VALUES = st.recursive(
    SCALARS,
    lambda children: (
        st.lists(children, max_size=3)
        | st.tuples(children)
        | st.dictionaries(KEYS, children, max_size=3)
    ),
    max_leaves=10,
)
WORDS = ["os", "OS", "roles", "a", "b", "eth0", "10", "1", "0", "ubu", "ubuntu", "x"]
PATTERNS = [
    "UBUNTU",
    "web",
    "web*",
    "w?b",
    "ub*",
    "ubu*",
    "ubun*",
    "*",
    "10.0.0.5",
    "fe80",
    "",
    "true",
    "none",
    "'os'",
    "ünï",
    "'q'",
    "ubu.*",
    "ubu.+",
    "ubu[n]tu",
    "(ubu|deb)",
    "ub+",
    "u.u",
    "web1?",
    "[ab]*",
    "x" * 300,
]
# Tokens mostly reuse document keys and values so targets reach real paths.
TOKENS = st.one_of(st.sampled_from(WORDS), st.sampled_from(PATTERNS))


def _paths(node, path=()):
    """Yield (path, node) for every node subdict_match can reach."""
    yield path, node
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _paths(value, path + (str(key),))
    elif isinstance(node, (list, tuple)):
        for idx, member in enumerate(node):
            # Lists are reached by index or by searching embedded dicts.
            yield from _paths(member, path + (str(idx),))
            if isinstance(member, dict):
                yield from _paths(member, path)


def _tails(node):
    if isinstance(node, dict):
        return [str(key) for key in node] or ["x"]
    if isinstance(node, (list, tuple)):
        return [str(member) for member in node] or ["x"]
    return [str(node)]


def _perturb(draw, text):
    choice = draw(st.integers(0, 8))
    if choice == 1:
        return text.upper()
    if choice == 2 and text:
        return text[: draw(st.integers(0, len(text)))] + "*"
    if choice == 3 and text:
        idx = draw(st.integers(0, len(text) - 1))
        return text[:idx] + "?" + text[idx + 1 :]
    if choice == 4:
        return text[: draw(st.integers(0, len(text)))] + ".*"
    if choice == 5:
        return text[: draw(st.integers(0, len(text)))] + ".+"
    if choice == 6:
        return f"'{text}'"
    if choice == 7:
        return draw(TOKENS)
    if choice == 8 and text:
        # A regex quantifier makes the preceding character optional.
        idx = draw(st.integers(0, len(text) - 1))
        return text[: idx + 1] + "?" + text[idx + 1 :]
    return text


@st.composite
def derived_targets(draw):
    data = draw(st.dictionaries(KEYS, VALUES, min_size=1, max_size=4))
    paths = [(path, node) for path, node in _paths(data) if path]
    path, node = draw(st.sampled_from(paths))
    tokens = [_perturb(draw, segment) for segment in path]
    tokens.append(_perturb(draw, draw(st.sampled_from(_tails(node)))))
    return data, ":".join(tokens)


@settings(max_examples=5000, deadline=None)
@given(
    target=derived_targets(),
    regex_match=st.booleans(),
    exact_match=st.booleans(),
)
def test_derived_plan_agrees_with_subdict_match(target, regex_match, exact_match):
    data, expr = target
    _assert_plan_agrees(data, expr, ":", regex_match, exact_match)


@settings(max_examples=5000, deadline=None)
@given(
    data=st.dictionaries(KEYS, VALUES, max_size=4),
    tokens=st.lists(TOKENS, min_size=1, max_size=4),
    delimiter=st.sampled_from([":", ":", "|"]),
    regex_match=st.booleans(),
    exact_match=st.booleans(),
)
def test_plan_agrees_with_subdict_match(
    data, tokens, delimiter, regex_match, exact_match
):
    _assert_plan_agrees(
        data, delimiter.join(tokens), delimiter, regex_match, exact_match
    )
