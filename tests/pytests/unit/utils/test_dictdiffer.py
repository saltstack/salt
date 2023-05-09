import pytest

import salt.utils.dictdiffer as dictdiffer

NONE = dictdiffer.RecursiveDictDiffer.NONE_VALUE
IGNORE_MISSING = True


@pytest.fixture
def differ(request):
    old, new, *ignore_missing = request.param
    try:
        ignore_missing = bool(ignore_missing.pop(0))
    except IndexError:
        ignore_missing = False
    return dictdiffer.RecursiveDictDiffer(old, new, ignore_missing)


@pytest.mark.parametrize("separator", [None, ":"])
@pytest.mark.parametrize(
    "differ,include_nested,expected",
    [
        (({"a": "a"}, {"a": "a", "b": "b"}), False, ["b"]),
        (({"a": "a"}, {"a": "a", "b": "b"}), True, ["b"]),
        (({"a": "a"}, {"a": "a", "b": None}), False, ["b"]),
        (({"a": {}}, {"a": {"b": "b"}}), False, ["a.b"]),
        (({"a": {}}, {"a": {"b": {}}}), False, ["a.b"]),
        (({"a": {}}, {"a": {"b": None}}), False, ["a.b"]),
        (({"a": "a"}, {"a": "a", "b": {}}), False, ["b"]),
        (({"a": "a"}, {"a": "a", "b": {"c": "c"}}), False, ["b"]),
        (({"a": "a"}, {"a": {"c": "c"}}), False, ["a.c"]),
        (({"a": {}}, {"a": {"b": {"c": "c"}}}), False, ["a.b"]),
        (({"a": {}}, {"a": {"b": {"c": "c"}}}), True, ["a.b", "a.b.c"]),
        (
            ({"a": {}}, {"a": {"b": {"c": {"d": "d"}}}}),
            True,
            ["a.b", "a.b.c", "a.b.c.d"],
        ),
    ],
    indirect=["differ"],
)
def test_added(differ, include_nested, expected, separator):
    if separator:
        expected = [x.replace(".", separator) for x in expected]
        assert (
            differ.added(separator=separator, include_nested=include_nested) == expected
        )
    else:
        assert differ.added(include_nested=include_nested) == expected


@pytest.mark.parametrize("separator", [None, ":"])
@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}), ["a"]),
        (({"a": "a"}, {"a": None}), ["a"]),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
            ),
            ["a.b"],
        ),
        (({"a": {"b": "b"}}, {"a": {"b": None}}), ["a.b"]),
        (({"a": "a"}, {"a": "a", "b": "b"}), []),
        (({"a": {}}, {"a": {"b": "b"}}), []),
        (({"a": "a", "b": "b"}, {"a": "a"}), []),
        (({"a": {"b": "b"}}, {"a": {}}), []),
    ],
    indirect=["differ"],
)
def test_changed(differ, expected, separator):
    if separator:
        expected = [x.replace(".", separator) for x in expected]
        assert differ.changed(separator=separator) == expected
    else:
        assert differ.changed() == expected


@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}), ["a"]),
        (({"a": "a"}, {"a": None}), ["a"]),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
            ),
            ["a.b"],
        ),
        (({"a": {"b": "b"}}, {"a": {"b": None}}), ["a.b"]),
        (({"a": "a"}, {"a": "a", "b": "b"}), ["b"]),
        (({"a": {}}, {"a": {"b": "b"}}), ["a.b"]),
        (({"a": "a", "b": "b"}, {"a": "a"}), ["b"]),
        (({"a": {"b": "b"}}, {"a": {}}), ["a.b"]),
    ],
    indirect=["differ"],
)
def test_changed_without_ignore_unset_values(differ, expected):
    differ.ignore_unset_values = False
    assert differ.changed() == expected


@pytest.mark.parametrize("separator", [None, ":"])
@pytest.mark.parametrize(
    "differ,include_nested,expected",
    [
        (({"a": "a", "b": "b"}, {"a": "a"}), False, ["b"]),
        (({"a": "a", "b": "b"}, {"a": "a"}), True, ["b"]),
        (({"a": "a", "b": None}, {"a": "a"}), False, ["b"]),
        (({"a": {"b": "b"}}, {"a": {}}), False, ["a.b"]),
        (({"a": {"b": {}}}, {"a": {}}), False, ["a.b"]),
        (({"a": {"b": None}}, {"a": {}}), False, ["a.b"]),
        (({"a": "a", "b": {}}, {"a": "a"}), False, ["b"]),
        (({"a": "a", "b": {"c": "c"}}, {"a": "a"}), False, ["b"]),
        (({"a": "z", "b": {"c": "c"}}, {"a": "a"}), False, ["b"]),
        (({"a": {}, "b": {"c": "c"}}, {"a": {"z": {"y": "y"}}}), False, ["b"]),
        (({"a": {"b": "b"}}, {"a": None}), False, ["a.b"]),
        (
            ({"a": {"b": {"c": {"d": "d"}}}}, {"a": {}}),
            True,
            ["a.b", "a.b.c", "a.b.c.d"],
        ),
    ],
    indirect=["differ"],
)
def test_removed(differ, include_nested, expected, separator):
    if separator:
        expected = [x.replace(".", separator) for x in expected]
        assert (
            differ.removed(separator=separator, include_nested=include_nested)
            == expected
        )
    else:
        assert differ.removed(include_nested=include_nested) == expected


@pytest.mark.parametrize("separator", [None, ":"])
@pytest.mark.parametrize(
    "differ,expected",
    [
        (
            ({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}),
            ["unchanged"],
        ),
        (({"a": "a"}, {"a": None}), []),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
            ),
            ["a.unchanged"],
        ),
        (({"a": {"b": "b"}}, {"a": {"b": None}}), []),
        (({"a": {}}, {"a": {"b": "b"}}), []),
        (({"a": "a", "b": "b"}, {"a": "a"}), ["a"]),
        (({"a": {"b": "b"}}, {"a": {}}), []),
    ],
    indirect=["differ"],
)
def test_unchanged(differ, expected, separator):
    if separator:
        expected = [x.replace(".", separator) for x in expected]
        assert differ.unchanged(separator=separator) == expected
    else:
        assert differ.unchanged() == expected


@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a"}, {"a": "a", "b": "b"}), {"b": {"old": NONE, "new": "b"}}),
        (
            ({"a": "a"}, {"a": "a", "b": "b"}, IGNORE_MISSING),
            {"b": {"old": NONE, "new": "b"}},
        ),
        (
            ({"a": "a"}, {"a": "a", "b": {"c": "c"}}),
            {"b": {"old": NONE, "new": {"c": "c"}}},
        ),
        (
            ({"a": "a"}, {"a": "a", "b": {"c": "c"}}, IGNORE_MISSING),
            {"b": {"old": NONE, "new": {"c": "c"}}},
        ),
        (
            ({"a": {}}, {"a": {"b": "b"}}),
            {"a": {"b": {"old": NONE, "new": "b"}}},
        ),
        (
            ({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}),
            {"a": {"old": "a", "new": "b"}},
        ),
        (
            (
                {"a": "a", "unchanged": True},
                {"a": "b", "unchanged": True},
                IGNORE_MISSING,
            ),
            {"a": {"old": "a", "new": "b"}},
        ),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
            ),
            {"a": {"b": {"old": "b", "new": "c"}}},
        ),
        (({"a": "a", "b": "b"}, {"a": "a"}), {"b": {"old": "b", "new": NONE}}),
        (({"a": "a", "b": "b"}, {"a": "a"}, IGNORE_MISSING), {}),
        (
            ({"a": {"b": "b"}}, {"a": {}}),
            {"a": {"b": {"old": "b", "new": NONE}}},
        ),
        (({"a": {"b": "b"}}, {"a": {}}, IGNORE_MISSING), {}),
        (
            ({"a": "a", "b": {"c": "c"}}, {"a": "a"}),
            {"b": {"old": {"c": "c"}, "new": NONE}},
        ),
        (({"a": "a", "b": {"c": "c"}}, {"a": "a"}, IGNORE_MISSING), {}),
    ],
    indirect=["differ"],
)
def test_diffs(differ, expected):
    assert differ.diffs == expected


@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a"}, {"a": "a", "b": "b"}), {"b": "b"}),
        (({"a": "a"}, {"a": "a", "b": {"c": "c"}}), {"b": {"c": "c"}}),
        (({"a": {}}, {"a": {"b": "b"}}), {"a": {"b": "b"}}),
        (
            ({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}),
            {"a": "b"},
        ),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
            ),
            {"a": {"b": "c"}},
        ),
        (({"a": "a", "b": "b"}, {"a": "a"}), {"b": NONE}),
        (({"a": {"b": "b"}}, {"a": {}}), {"a": {"b": NONE}}),
        (({"a": "a", "b": {"c": "c"}}, {"a": "a"}), {"b": NONE}),
    ],
    indirect=["differ"],
)
def test_new_values(differ, expected):
    assert differ.new_values == expected


@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a"}, {"a": "a", "b": "b"}), {"b": NONE}),
        (({"a": "a"}, {"a": "a", "b": {"c": "c"}}), {"b": NONE}),
        (({"a": {}}, {"a": {"b": "b"}}), {"a": {"b": NONE}}),
        (
            ({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}),
            {"a": "a"},
        ),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
            ),
            {"a": {"b": "b"}},
        ),
        (({"a": "a", "b": "b"}, {"a": "a"}), {"b": "b"}),
        (({"a": {"b": "b"}}, {"a": {}}), {"a": {"b": "b"}}),
        (({"a": "a", "b": {"c": "c"}}, {"a": "a"}), {"b": {"c": "c"}}),
    ],
    indirect=["differ"],
)
def test_old_values(differ, expected):
    assert differ.old_values == expected


@pytest.mark.parametrize(
    "differ,expected",
    [
        (({"a": "a"}, {"a": "a", "b": "b"}), "b from nothing to 'b'"),
        (
            ({"a": "a"}, {"a": "a", "b": {"c": "c"}}),
            "b from nothing to {'c': 'c'}",
        ),
        (({"a": {}}, {"a": {"b": "b"}}), "a:\n  b from nothing to 'b'"),
        (
            ({"a": "a", "unchanged": True}, {"a": "b", "unchanged": True}),
            "a from 'a' to 'b'",
        ),
        (
            (
                {"a": {"b": "b", "unchanged": True}},
                {"a": {"b": "c", "unchanged": True}},
            ),
            "a:\n  b from 'b' to 'c'",
        ),
        (({"a": "a", "b": "b"}, {"a": "a"}), "b from 'b' to nothing"),
        (({"a": {"b": "b"}}, {"a": {}}), "a:\n  b from 'b' to nothing"),
        (
            ({"a": "a", "b": {"c": "c"}}, {"a": "a"}),
            "b from {'c': 'c'} to nothing",
        ),
        (
            ({"a": {"b": "b"}, "c": "c"}, {"a": {}, "c": "d"}),
            "a:\n  b from 'b' to nothing\nc from 'c' to 'd'",
        ),
        (({"a": []}, {"a": ["b", "c"]}), "a from '' to 'b, c'"),
        (({"a": ["b", "c"]}, {"a": []}), "a from 'b, c' to ''"),
    ],
    indirect=["differ"],
)
def test_changes_str(differ, expected):
    assert differ.changes_str == expected
