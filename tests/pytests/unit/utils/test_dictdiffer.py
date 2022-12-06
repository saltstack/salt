import pytest

import salt.utils.dictdiffer as dictdiffer

NONE = dictdiffer.RecursiveDictDiffer.NONE_VALUE


@pytest.fixture
def differ(request):
    old, new, ignore_missing = request.param
    return dictdiffer.RecursiveDictDiffer(old, new, ignore_missing)


@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a"}, {"a": "a", "b": "b"}, False), ["b"]),
        (({"a": "a"}, {"a": "a", "b": None}, False), ["b"]),
        (({"a": {}}, {"a": {"b": "b"}}, False), ["a.b"]),
        (({"a": {}}, {"a": {"b": None}}, False), ["a.b"]),
    ],
    indirect=["differ"],
)
def test_added(differ, expected):
    assert differ.added() == expected


@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}, False), ["a"]),
        (({"a": "a"}, {"a": None}, False), ["a"]),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
                False,
            ),
            ["a.b"],
        ),
        (({"a": {"b": "b"}}, {"a": {"b": None}}, False), ["a.b"]),
        (({"a": "a"}, {"a": "a", "b": "b"}, False), []),
        (({"a": {}}, {"a": {"b": "b"}}, False), []),
        (({"a": "a", "b": "b"}, {"a": "a"}, False), []),
        (({"a": {"b": "b"}}, {"a": {}}, False), []),
    ],
    indirect=["differ"],
)
def test_changed(differ, expected):
    assert differ.changed() == expected


@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}, False), ["a"]),
        (({"a": "a"}, {"a": None}, False), ["a"]),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
                False,
            ),
            ["a.b"],
        ),
        (({"a": {"b": "b"}}, {"a": {"b": None}}, False), ["a.b"]),
        (({"a": "a"}, {"a": "a", "b": "b"}, False), ["b"]),
        (({"a": {}}, {"a": {"b": "b"}}, False), ["a.b"]),
        (({"a": "a", "b": "b"}, {"a": "a"}, False), ["b"]),
        (({"a": {"b": "b"}}, {"a": {}}, False), ["a.b"]),
    ],
    indirect=["differ"],
)
def test_changed_without_ignore_unset_values(differ, expected):
    differ.ignore_unset_values = False
    assert differ.changed() == expected


@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a", "b": "b"}, {"a": "a"}, False), ["b"]),
        (({"a": "a", "b": None}, {"a": "a"}, False), ["b"]),
        (({"a": {"b": "b"}}, {"a": {}}, False), ["a.b"]),
        (({"a": {"b": {}}}, {"a": {}}, False), ["a.b"]),
        (({"a": {"b": None}}, {"a": {}}, False), ["a.b"]),
        (({"a": "a", "b": {}}, {"a": "a"}, False), ["b"]),
        (({"a": "a", "b": {"c": "c"}}, {"a": "a"}, False), ["b"]),
        (({"a": "z", "b": {"c": "c"}}, {"a": "a"}, False), ["b"]),
    ],
    indirect=["differ"],
)
def test_removed(differ, expected):
    assert differ.removed() == expected


@pytest.mark.parametrize(
    "differ,expected",
    [
        (
            ({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}, False),
            ["unchanged"],
        ),
        (({"a": "a"}, {"a": None}, False), []),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
                False,
            ),
            ["a.unchanged"],
        ),
        (({"a": {"b": "b"}}, {"a": {"b": None}}, False), []),
        (({"a": {}}, {"a": {"b": "b"}}, False), []),
        (({"a": "a", "b": "b"}, {"a": "a"}, False), ["a"]),
        (({"a": {"b": "b"}}, {"a": {}}, False), []),
    ],
    indirect=["differ"],
)
def test_unchanged(differ, expected):
    assert differ.unchanged() == expected


@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a"}, {"a": "a", "b": "b"}, False), {"b": {"old": NONE, "new": "b"}}),
        (({"a": "a"}, {"a": "a", "b": "b"}, True), {"b": {"old": NONE, "new": "b"}}),
        (
            ({"a": "a"}, {"a": "a", "b": {"c": "c"}}, False),
            {"b": {"old": NONE, "new": {"c": "c"}}},
        ),
        (
            ({"a": "a"}, {"a": "a", "b": {"c": "c"}}, True),
            {"b": {"old": NONE, "new": {"c": "c"}}},
        ),
        (
            ({"a": {}}, {"a": {"b": "b"}}, False),
            {"a": {"b": {"old": NONE, "new": "b"}}},
        ),
        (
            ({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}, False),
            {"a": {"old": "a", "new": "b"}},
        ),
        (
            ({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}, True),
            {"a": {"old": "a", "new": "b"}},
        ),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
                False,
            ),
            {"a": {"b": {"old": "b", "new": "c"}}},
        ),
        (({"a": "a", "b": "b"}, {"a": "a"}, False), {"b": {"old": "b", "new": NONE}}),
        (({"a": "a", "b": "b"}, {"a": "a"}, True), {}),
        (
            ({"a": {"b": "b"}}, {"a": {}}, False),
            {"a": {"b": {"old": "b", "new": NONE}}},
        ),
        (({"a": {"b": "b"}}, {"a": {}}, True), {}),
        (
            ({"a": "a", "b": {"c": "c"}}, {"a": "a"}, False),
            {"b": {"old": {"c": "c"}, "new": NONE}},
        ),
        (({"a": "a", "b": {"c": "c"}}, {"a": "a"}, True), {}),
    ],
    indirect=["differ"],
)
def test_diffs(differ, expected):
    assert differ.diffs == expected


@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a"}, {"a": "a", "b": "b"}, False), {"b": "b"}),
        (({"a": "a"}, {"a": "a", "b": {"c": "c"}}, False), {"b": {"c": "c"}}),
        (({"a": {}}, {"a": {"b": "b"}}, False), {"a": {"b": "b"}}),
        (
            ({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}, False),
            {"a": "b"},
        ),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
                False,
            ),
            {"a": {"b": "c"}},
        ),
        (({"a": "a", "b": "b"}, {"a": "a"}, False), {"b": NONE}),
        (({"a": {"b": "b"}}, {"a": {}}, False), {"a": {"b": NONE}}),
        (({"a": "a", "b": {"c": "c"}}, {"a": "a"}, False), {"b": NONE}),
    ],
    indirect=["differ"],
)
def test_new_values(differ, expected):
    assert differ.new_values == expected


@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a"}, {"a": "a", "b": "b"}, False), {"b": NONE}),
        (({"a": "a"}, {"a": "a", "b": {"c": "c"}}, False), {"b": NONE}),
        (({"a": {}}, {"a": {"b": "b"}}, False), {"a": {"b": NONE}}),
        (
            ({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}, False),
            {"a": "a"},
        ),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
                False,
            ),
            {"a": {"b": "b"}},
        ),
        (({"a": "a", "b": "b"}, {"a": "a"}, False), {"b": "b"}),
        (({"a": {"b": "b"}}, {"a": {}}, False), {"a": {"b": "b"}}),
        (({"a": "a", "b": {"c": "c"}}, {"a": "a"}, False), {"b": {"c": "c"}}),
    ],
    indirect=["differ"],
)
def test_old_values(differ, expected):
    assert differ.old_values == expected


@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a"}, {"a": "a", "b": "b"}, False), "b from nothing to 'b'"),
        (
            ({"a": "a"}, {"a": "a", "b": {"c": "c"}}, False),
            "b from nothing to {'c': 'c'}",
        ),
        (({"a": {}}, {"a": {"b": "b"}}, False), "a:\n  b from nothing to 'b'"),
        (
            ({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}, False),
            "a from 'a' to 'b'",
        ),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
                False,
            ),
            "a:\n  b from 'b' to 'c'",
        ),
        (({"a": "a", "b": "b"}, {"a": "a"}, False), "b from 'b' to nothing"),
        (({"a": {"b": "b"}}, {"a": {}}, False), "a:\n  b from 'b' to nothing"),
        (
            ({"a": "a", "b": {"c": "c"}}, {"a": "a"}, False),
            "b from {'c': 'c'} to nothing",
        ),
        (
            ({"a": {"b": "b"}, "c": "c"}, {"a": {}, "c": "d"}, False),
            "a:\n  b from 'b' to nothing\nc from 'c' to 'd'",
        ),
    ],
    indirect=["differ"],
)
def test_changes_str(differ, expected):
    assert differ.changes_str == expected
