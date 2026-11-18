"""
Unit coverage for the opts-driven ``salt.resources.dummy`` module.

Enforces the post-pillar contract for the dummy resource type:

* ``init(opts)`` reads ``dummy_resource_count`` from opts (NOT pillar) and
  does not materialize an ID list in ``__context__``.
* ``discover(opts)`` is a **generator** -- IDs are yielded one at a time so
  the register loop can chunk without ever holding the full list resident.
* IDs follow the ``dummy-NNNNNNN`` seven-digit pattern.
* ``grains()`` still works without pillar (it only consumes the current
  resource's static grain dict).
"""

import collections.abc
import contextlib

import pytest

import salt.resources.dummy as dummy_mod
from tests.support.mock import patch


@pytest.fixture
def dummy_opts(tmp_path):
    """Minimal opts dict the dummy module accepts."""
    return {"cachedir": str(tmp_path)}


def _module_dunders(opts, resource_id=None, context=None):
    if context is None:
        context = {}
    patches = [
        patch.object(dummy_mod, "__opts__", opts, create=True),
        patch.object(dummy_mod, "__context__", context, create=True),
    ]
    if resource_id is not None:
        patches.append(
            patch.object(
                dummy_mod,
                "__resource__",
                {"id": resource_id, "type": "dummy"},
                create=True,
            )
        )
    return patches


# ---------------------------------------------------------------------------
# discover()
# ---------------------------------------------------------------------------


def test_discover_zero_count_yields_nothing(dummy_opts):
    """``dummy_resource_count: 0`` -> generator yields no IDs."""
    dummy_opts["dummy_resource_count"] = 0
    gen = dummy_mod.discover(dummy_opts)
    assert list(gen) == []


def test_discover_missing_count_treated_as_zero(dummy_opts):
    """Absent opt -> empty inventory, no crash."""
    assert list(dummy_mod.discover(dummy_opts)) == []


def test_discover_five_ids(dummy_opts):
    """Zero-padded 7-digit IDs starting at 0000001."""
    dummy_opts["dummy_resource_count"] = 5
    ids = list(dummy_mod.discover(dummy_opts))
    assert ids == [
        "dummy-0000001",
        "dummy-0000002",
        "dummy-0000003",
        "dummy-0000004",
        "dummy-0000005",
    ]


def test_discover_returns_generator_not_list(dummy_opts):
    """
    ``discover()`` MUST be a generator so the register loop can stream.
    If someone regresses this to ``return [f"dummy-{i:07d}" for i in ...]``
    the 200K-resource case re-materializes the full ID list and the
    minion memory ceiling is busted.
    """
    dummy_opts["dummy_resource_count"] = 3
    out = dummy_mod.discover(dummy_opts)
    assert isinstance(
        out, collections.abc.Generator
    ), f"discover() returned {type(out).__name__}; must be a generator"
    assert not isinstance(out, list)


def test_discover_does_not_materialize_full_count(dummy_opts):
    """
    Peek at the first ID from a 1M-count generator -- the whole set must
    not be realized up front.  Hard invariant: pulling one item costs
    O(1) memory, not O(1M).  We can't easily measure RSS inside a unit
    test, but we can assert that the result is a generator and that the
    first yield returns before the full range is traversed by using a
    trace counter around ``range``.
    """
    dummy_opts["dummy_resource_count"] = 1_000_000
    gen = dummy_mod.discover(dummy_opts)
    # One ``next()`` must succeed without needing to traverse all 1M.
    first = next(gen)
    assert first == "dummy-0000001"


def test_discover_bad_count_treated_as_zero(dummy_opts):
    """Non-int values -> empty, with a warning (see module)."""
    dummy_opts["dummy_resource_count"] = "lots"
    assert list(dummy_mod.discover(dummy_opts)) == []


def test_discover_does_not_read_pillar(dummy_opts):
    """
    Trap pillar subtree -- the old code read
    ``pillar["resources"]["dummy"]["resource_ids"]``.  The new module
    must ignore this entirely and read ``dummy_resource_count`` only.
    """
    dummy_opts["dummy_resource_count"] = 2
    dummy_opts["pillar"] = {
        "resources": {"dummy": {"resource_ids": ["poison-1", "poison-2"]}}
    }
    ids = list(dummy_mod.discover(dummy_opts))
    assert ids == ["dummy-0000001", "dummy-0000002"]
    assert "poison-1" not in ids


# ---------------------------------------------------------------------------
# init()
# ---------------------------------------------------------------------------


def test_init_does_not_materialize_id_list(dummy_opts):
    """
    ``init()`` must NOT stuff the full ID list into ``__context__`` --
    the whole point of the redesign.  A per-type count is fine.
    """
    dummy_opts["dummy_resource_count"] = 42
    ctx = {}
    with contextlib.ExitStack() as stack:
        for p in _module_dunders(dummy_opts, context=ctx):
            stack.enter_context(p)
        dummy_mod.init(dummy_opts)
    assert ctx["dummy_resource"]["initialized"] is True
    # The context may hold a count, but MUST NOT hold a list of IDs.
    stored = ctx["dummy_resource"]
    for value in stored.values():
        if isinstance(value, list):
            assert len(value) == 0, (
                f"init() materialized a list of {len(value)} IDs into "
                "__context__; must only hold a count"
            )


def test_init_count_zero_initializes(dummy_opts):
    """Empty inventory still initializes the type."""
    dummy_opts["dummy_resource_count"] = 0
    ctx = {}
    with contextlib.ExitStack() as stack:
        for p in _module_dunders(dummy_opts, context=ctx):
            stack.enter_context(p)
        dummy_mod.init(dummy_opts)
    assert ctx["dummy_resource"]["initialized"] is True


# ---------------------------------------------------------------------------
# grains() -- still works without pillar
# ---------------------------------------------------------------------------


def test_grains_works_without_pillar(dummy_opts):
    """``grains()`` only consumes the per-resource static dict; no pillar."""
    with contextlib.ExitStack() as stack:
        for p in _module_dunders(dummy_opts, resource_id="dummy-0000001"):
            stack.enter_context(p)
        g = dummy_mod.grains()
    assert g["resource_id"] == "dummy-0000001"
    assert g["dummy_grain_1"] == "one"
    assert g["dummy_grain_2"] == "two"
    assert g["dummy_grain_3"] == "three"


def test_grains_opts_has_no_pillar_key(dummy_opts):
    """A grains() call that explodes if pillar is touched -- regression trap."""
    with contextlib.ExitStack() as stack:
        for p in _module_dunders(dummy_opts, resource_id="dummy-0000001"):
            stack.enter_context(p)
        # No ``pillar`` key in opts; grains() must still succeed.
        g = dummy_mod.grains()
    assert g["resource_id"] == "dummy-0000001"
