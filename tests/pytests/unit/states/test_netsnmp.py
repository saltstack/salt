"""
Unit tests for the netsnmp state.
"""

import pytest

import salt.states.netsnmp as netsnmp


@pytest.fixture
def configure_loader_modules():
    return {netsnmp: {}}


def test_expand_config_without_defaults():
    # The state's optional ``defaults`` is None when unset -- must not crash.
    assert netsnmp._expand_config({"location": "DC1"}, None) == {"location": "DC1"}


def test_expand_config_merges_defaults():
    # Per-config values win over defaults on a key collision.
    assert netsnmp._expand_config(
        {"location": "DC1"}, {"contact": "noc", "location": "old"}
    ) == {"contact": "noc", "location": "DC1"}


def test_clear_community_details_normalizes_mode():
    # ``read-write``/``write`` -> ``rw``; case-folded; the old ``get["mode"]``
    # typo raised TypeError for every one of these.
    assert netsnmp._clear_community_details({"mode": "read-write"})["mode"] == "rw"
    assert netsnmp._clear_community_details({"mode": "RO"})["mode"] == "ro"
    # Missing mode -> default read-only.
    assert netsnmp._clear_community_details({})["mode"] == "ro"
    # Unrecognised mode -> default read-only.
    assert netsnmp._clear_community_details({"mode": "bogus"})["mode"] == "ro"


def test_compute_diff_updated_value_not_dropped():
    # location "OldTown" -> "NewTown": both valid strings. Regression: the old
    # dead ``elif not fun(curr)`` branch dropped this, so the change was never
    # pushed and the state falsely reported success.
    diff = netsnmp._compute_diff({"location": "OldTown"}, {"location": "NewTown"})
    assert diff == {"updated": {"location": "NewTown"}}


def test_compute_diff_added_and_removed():
    assert netsnmp._compute_diff({}, {"location": "DC1"}) == {
        "added": {"location": "DC1"}
    }
    assert netsnmp._compute_diff({"location": "DC1"}, {}) == {
        "removed": {"location": "DC1"}
    }


def test_compute_diff_community_updated():
    # The community mapping is diffed via _valid_dict; a mode change on an
    # existing community is a valid-dict -> valid-dict update and must land in
    # "updated" (exercises the else branch for the dict case, not just str).
    diff = netsnmp._compute_diff(
        {"community": {"public": {"mode": "ro"}}},
        {"community": {"public": {"mode": "rw"}}},
    )
    assert diff == {"updated": {"community": {"public": {"mode": "rw"}}}}
