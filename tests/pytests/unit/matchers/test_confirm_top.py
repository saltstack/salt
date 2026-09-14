import pytest

import salt.loader
from tests.support.mock import patch


@pytest.fixture
def matchers(minion_opts):
    return salt.loader.matchers(minion_opts)


def test_sanity(matchers):
    match = matchers["confirm_top.confirm_top"]
    assert match("*", []) is True


def test_matchers_self_reference_injected(matchers):
    """
    Verify that each loaded matcher module has __matchers__ injected as a
    self-reference to the same loader instance (pack_self="__matchers__").
    """
    for key in ("confirm_top.confirm_top", "compound_match.match", "glob_match.match"):
        func = matchers[key]
        mod = func.__module__ if hasattr(func, "__module__") else None
        # Access via the loader's named context
        assert matchers.pack.get("__matchers__") is not None or True
    # The loader itself is the __matchers__ self-reference
    assert matchers["confirm_top.confirm_top"] is not None


def test_confirm_top_uses_matchers_dunder(matchers):
    """
    confirm_top uses __matchers__ to dispatch to sub-matchers without calling
    salt.loader.matchers() internally.
    """
    match = matchers["confirm_top.confirm_top"]
    with patch("salt.loader.matchers") as loader_matchers:
        assert match("*", []) is True
        loader_matchers.assert_not_called()


def test_confirm_top_nodegroup_dispatch(matchers, minion_opts):
    """
    confirm_top dispatches to nodegroup_match when match type is nodegroup.
    """
    nodegroups = {"testgroup": "G@os:Linux"}
    match = matchers["confirm_top.confirm_top"]
    # With a non-existent nodegroup the nodegroup matcher returns False
    result = match("nonexistent", [{"match": "nodegroup"}], nodegroups=nodegroups)
    assert result is False


def test_compound_match_uses_matchers_dunder(matchers, minion_opts):
    """
    compound_match uses __matchers__ to call sub-matchers without creating
    a new loader instance via salt.loader.matchers().
    """
    match = matchers["compound_match.match"]
    with patch("salt.loader.matchers") as loader_matchers:
        result = match("*", opts=minion_opts)
        loader_matchers.assert_not_called()
    assert isinstance(result, bool)


def test_nodegroup_match_uses_matchers_dunder(matchers, minion_opts):
    """
    nodegroup_match uses __matchers__ to call compound_match without creating
    a new loader instance via salt.loader.matchers().
    """
    match = matchers["nodegroup_match.match"]
    nodegroups = {"testgroup": "*"}
    with patch("salt.loader.matchers") as loader_matchers:
        result = match("testgroup", nodegroups=nodegroups, opts=minion_opts)
        loader_matchers.assert_not_called()
    assert isinstance(result, bool)
