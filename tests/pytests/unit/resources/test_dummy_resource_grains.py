"""
Unit tests for ``salt.resources.dummy``'s per-resource grain plugin.

Each individual dummy resource has its own ``grains`` function (the resource
analogue of a minion grain plugin). The minion's ``_thread_return`` swaps
``__grains__`` for ``resource_funcs[f"{type}.grains"]()`` before running a
function for a resource target, so this module is what eventually populates
``__grains__`` for a dispatched ``grains.items`` call against a dummy resource.
"""

import contextlib

import pytest

import salt.resources.dummy as dummy_mod
from tests.support.mock import patch

_RESOURCE_ID = "dummy-01"


def _module_dunders(opts, resource_id):
    """Inject the dunders the resource loader normally provides."""
    return [
        patch.object(dummy_mod, "__opts__", opts, create=True),
        patch.object(
            dummy_mod, "__resource__", {"id": resource_id, "type": "dummy"}, create=True
        ),
    ]


@pytest.fixture
def dummy_opts(tmp_path):
    return {"cachedir": str(tmp_path)}


def test_grains_returns_expected_keys(dummy_opts):
    """``grains()`` must return the resource's static grain set keyed by id."""
    with contextlib.ExitStack() as stack:
        for p in _module_dunders(dummy_opts, _RESOURCE_ID):
            stack.enter_context(p)
        result = dummy_mod.grains()
    assert result == {
        "dummy_grain_1": "one",
        "dummy_grain_2": "two",
        "dummy_grain_3": "three",
        "resource_id": _RESOURCE_ID,
    }


def test_grains_resource_id_reflects_current_resource(dummy_opts):
    """
    ``grains()`` reads the active resource id from ``__resource__`` (set by
    ``_thread_return`` via ``resource_ctxvar``); two different resources must
    see two different ``resource_id`` grain values.
    """
    with contextlib.ExitStack() as stack:
        for p in _module_dunders(dummy_opts, "dummy-02"):
            stack.enter_context(p)
        result = dummy_mod.grains()
    assert result["resource_id"] == "dummy-02"


def test_grains_persists_to_state_cache(dummy_opts):
    """
    ``grains()`` writes the rendered grain dict into the per-resource state
    cache (``state["grains_cache"]``) so that ``grains_refresh`` has something
    to invalidate. After one call the cachefile must contain the same dict.
    """
    with contextlib.ExitStack() as stack:
        for p in _module_dunders(dummy_opts, _RESOURCE_ID):
            stack.enter_context(p)
        dummy_mod.grains()
        # Reach back into the state file via the module's own helper.
        state = dummy_mod._load_state(dummy_opts, _RESOURCE_ID)
    assert state.get("grains_cache") == {
        "dummy_grain_1": "one",
        "dummy_grain_2": "two",
        "dummy_grain_3": "three",
        "resource_id": _RESOURCE_ID,
    }


def test_grains_refresh_invalidates_and_returns_fresh(dummy_opts):
    """
    ``grains_refresh()`` must drop the cached entry and re-derive the grain
    dict — the next ``grains()`` call sees a fresh dict, not a stale snapshot.
    """
    with contextlib.ExitStack() as stack:
        for p in _module_dunders(dummy_opts, _RESOURCE_ID):
            stack.enter_context(p)
        first = dummy_mod.grains()
        # Mutate the cached state to a sentinel; if grains_refresh truly
        # invalidates it, the sentinel must not survive.
        state = dummy_mod._load_state(dummy_opts, _RESOURCE_ID)
        state["grains_cache"] = {"stale": True}
        dummy_mod._save_state(dummy_opts, _RESOURCE_ID, state)
        refreshed = dummy_mod.grains_refresh()
    assert refreshed == first, "grains_refresh must produce the canonical dict"
    assert "stale" not in refreshed, "grains_refresh must clear the stale cache"
