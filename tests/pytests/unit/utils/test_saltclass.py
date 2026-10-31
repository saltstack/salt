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
