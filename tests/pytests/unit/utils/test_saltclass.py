import textwrap

import pytest

import salt.utils.saltclass as saltclass


def test_dict_merge_list_override_single_class_50755():
    """
    A leading '^' override marker on a list must be honoured even when the
    target dict has no existing list to override (single-class case).

    This mirrors the production call in expanded_dict_from_minion, where the
    caller does dict_merge(pillars_dict, exp_dict) with an initially empty
    pillars_dict and the override list nested under the "pillars" key.
    """
    assert saltclass.dict_merge({}, {"pillars": {"pkgs": ["^", "three"]}}) == {
        "pillars": {"pkgs": ["three"]}
    }


def test_dict_merge_list_override_deeper_nesting_50755():
    """
    The override marker must be stripped for a list nested at arbitrary depth
    below an absent key, not only directly under "pillars".
    """
    assert saltclass.dict_merge({}, {"a": {"b": ["^", "x"]}}) == {"a": {"b": ["x"]}}


def test_dict_merge_list_override_key_present_50755():
    """
    Inverse / must-not-regress: the override marker already worked when the
    target dict contained a matching list. This passes with and without the
    fix and guards the existing list+list code path.
    """
    assert saltclass.dict_merge(
        {"pillars": {"pkgs": ["one", "two"]}},
        {"pillars": {"pkgs": ["^", "three"]}},
    ) == {"pillars": {"pkgs": ["three"]}}


def test_dict_merge_plain_list_key_absent_no_marker_50755():
    """
    Inverse / must-not-regress: a marker-free list assigned into an absent key
    must be copied through verbatim. Passes with and without the fix.
    """
    assert saltclass.dict_merge({}, {"pkgs": ["one", "two"]}) == {
        "pkgs": ["one", "two"]
    }


def test_dict_merge_empty_list_key_absent_50755():
    """
    Peripheral coverage: an empty list assigned into an absent key must not
    raise IndexError while checking for the '^' marker.
    """
    assert saltclass.dict_merge({}, {"pkgs": []}) == {"pkgs": []}


def test_dict_merge_plain_extend_key_present_50755():
    """
    Peripheral coverage: marker-free lists on a present key are extended, not
    replaced. This is the default (non-override) merge behaviour.
    """
    assert saltclass.dict_merge({"pkgs": ["one"]}, {"pkgs": ["two"]}) == {
        "pkgs": ["one", "two"]
    }


@pytest.fixture
def saltclass_tree(tmp_path):
    """
    Write ``classes`` and a minion node to a saltclass tree and return the
    ``salt_data`` that ``get_pillars`` expects.
    """

    def _write(classes, node):
        (tmp_path / "classes").mkdir()
        (tmp_path / "nodes").mkdir()
        for name, text in classes.items():
            (tmp_path / "classes" / f"{name}.yml").write_text(textwrap.dedent(text))
        (tmp_path / "nodes" / "minion.yml").write_text(textwrap.dedent(node))
        return {
            "path": str(tmp_path),
            "__opts__": {},
            "__salt__": {},
            "__grains__": {},
            "__pillar__": {},
            "minion_id": "minion",
        }

    return _write


def test_get_pillars_merged_list_has_no_duplicates_70022(saltclass_tree):
    """
    Merging class pillars into __pillar__ must not alter the class definitions
    that are merged again to build the final pillars. Otherwise the entries of
    the second class show up twice.
    """
    salt_data = saltclass_tree(
        {
            "test1": """
            pillars:
              data:
                - data 1 from test1
                - data 2 from test1
            """,
            "test2": """
            pillars:
              data:
                - data 1 from test2
                - data 2 from test2
            """,
        },
        """
        environment: base

        classes:
          - test1
          - test2
        """,
    )

    assert saltclass.get_pillars("minion", salt_data)["data"] == [
        "data 1 from test1",
        "data 2 from test1",
        "data 1 from test2",
        "data 2 from test2",
    ]


def test_get_pillars_class_list_override_70022(saltclass_tree):
    """
    Merging class pillars into __pillar__ must not strip a '^' marker from the
    class definition, or the final merge turns the override into an extend.
    """
    salt_data = saltclass_tree(
        {
            "test1": """
            pillars:
              data:
                - from test1
            """,
            "test2": """
            pillars:
              data:
                - ^
                - from test2
            """,
            "test3": """
            pillars:
              data:
                - from test3
            """,
        },
        """
        classes:
          - test1
          - test2
          - test3
        """,
    )

    assert saltclass.get_pillars("minion", salt_data)["data"] == [
        "from test2",
        "from test3",
    ]
