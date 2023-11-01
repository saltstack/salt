import pytest

from salt.utils.dictdiffer import RecursiveDictDiffer
from salt.utils.listdiffer import list_diff


@pytest.fixture
def get_old_list():
    return [
        {"key": 1, "value": "foo1", "int_value": 101},
        {"key": 2, "value": "foo2", "int_value": 102},
        {"key": 3, "value": "foo3", "int_value": 103},
    ]


@pytest.fixture
def get_new_list():
    return [
        {"key": 1, "value": "foo1", "int_value": 101},
        {"key": 2, "value": "foo2", "int_value": 112},
        {"key": 5, "value": "foo5", "int_value": 105},
    ]


@pytest.fixture
def get_list_diff(get_old_list, get_new_list):
    return list_diff(get_old_list, get_new_list, key="key")


def test_added(get_list_diff):
    assert len(get_list_diff.added) == 1
    assert get_list_diff.added[0] == {"key": 5, "value": "foo5", "int_value": 105}


def test_removed(get_list_diff):
    assert len(get_list_diff.removed) == 1
    assert get_list_diff.removed[0] == {"key": 3, "value": "foo3", "int_value": 103}


def test_diffs(get_list_diff):
    assert len(get_list_diff.diffs) == 3
    assert get_list_diff.diffs[0] == {2: {"int_value": {"new": 112, "old": 102}}}

    # Added items
    assert get_list_diff.diffs[1] == {
        5: {
            "int_value": {"new": 105, "old": RecursiveDictDiffer.NONE_VALUE},
            "key": {"new": 5, "old": RecursiveDictDiffer.NONE_VALUE},
            "value": {"new": "foo5", "old": RecursiveDictDiffer.NONE_VALUE},
        }
    }

    # Removed items
    assert get_list_diff.diffs[2] == {
        3: {
            "int_value": {"new": RecursiveDictDiffer.NONE_VALUE, "old": 103},
            "key": {"new": RecursiveDictDiffer.NONE_VALUE, "old": 3},
            "value": {"new": RecursiveDictDiffer.NONE_VALUE, "old": "foo3"},
        }
    }


def test_new_values(get_list_diff):
    assert len(get_list_diff.new_values) == 2
    assert get_list_diff.new_values[0] == {"key": 2, "int_value": 112}
    assert get_list_diff.new_values[1] == {"key": 5, "value": "foo5", "int_value": 105}


def test_old_values(get_list_diff):
    assert len(get_list_diff.old_values) == 2
    assert get_list_diff.old_values[0] == {"key": 2, "int_value": 102}
    assert get_list_diff.old_values[1] == {"key": 3, "value": "foo3", "int_value": 103}


def test_changed_all(get_list_diff):
    assert get_list_diff.changed(selection="all") == [
        "key.2.int_value",
        "key.5.int_value",
        "key.5.value",
        "key.3.int_value",
        "key.3.value",
    ]


def test_changed_intersect(get_list_diff):
    assert get_list_diff.changed(selection="intersect") == ["key.2.int_value"]


def test_changes_str(get_list_diff):
    expected = """\tidentified by key 2:
\tint_value from 102 to 112
\tidentified by key 3:
\twill be removed
\tidentified by key 5:
\twill be added
"""
    assert get_list_diff.changes_str == expected


def test_intersect(get_list_diff):
    expected = [
        {
            "key": 1,
            "old": {"key": 1, "value": "foo1", "int_value": 101},
            "new": {"key": 1, "value": "foo1", "int_value": 101},
        },
        {
            "key": 2,
            "old": {"key": 2, "value": "foo2", "int_value": 102},
            "new": {"key": 2, "value": "foo2", "int_value": 112},
        },
    ]
    test_isect = get_list_diff.intersect
    assert test_isect == expected


def test_remove_diff_intersect(get_list_diff):
    expected = [
        {
            "key": 1,
            "old": {"key": 1, "int_value": 101},
            "new": {"key": 1, "int_value": 101},
        },
        {
            "key": 2,
            "old": {"key": 2, "int_value": 102},
            "new": {"key": 2, "int_value": 112},
        },
    ]

    get_list_diff.remove_diff(diff_key="value")
    test_isect = get_list_diff.intersect
    assert test_isect == expected


def test_remove_diff_removed(get_list_diff):
    expected = [
        {
            "key": 1,
            "old": {"key": 1, "value": "foo1", "int_value": 101},
            "new": {"key": 1, "value": "foo1", "int_value": 101},
        },
        {
            "key": 2,
            "old": {"key": 2, "value": "foo2", "int_value": 102},
            "new": {"key": 2, "value": "foo2", "int_value": 112},
        },
    ]
    get_list_diff.remove_diff(diff_key="value", diff_list="removed")
    test_isect = get_list_diff.intersect
    assert test_isect == expected


def test_changes_str2(get_list_diff):
    expected = """  key=2 (updated):
    int_value from 102 to 112
  key=3 (removed)
  key=5 (added): {'key': 5, 'value': 'foo5', 'int_value': 105}"""
    test_changes = get_list_diff.changes_str2
    assert test_changes == expected


def test_current_list(get_list_diff):
    expected = [
        {"key": 1, "value": "foo1", "int_value": 101},
        {"key": 2, "value": "foo2", "int_value": 102},
        {"key": 3, "value": "foo3", "int_value": 103},
    ]
    test_curr_list = get_list_diff.current_list
    assert test_curr_list == expected


def test_new_list(get_list_diff):
    expected = [
        {"key": 1, "value": "foo1", "int_value": 101},
        {"key": 2, "value": "foo2", "int_value": 112},
        {"key": 5, "value": "foo5", "int_value": 105},
    ]
    test_new_list = get_list_diff.new_list
    assert test_new_list == expected
