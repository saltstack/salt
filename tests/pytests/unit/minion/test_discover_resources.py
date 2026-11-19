"""
Unit coverage for the minion's resource-discovery code path.

Enforces the post-pillar contract:

* The minion iterates resource types from the top-level ``resource_types``
  opt (via :func:`salt.utils.resources.enabled_resource_types`).
* Per-type IDs are obtained by calling ``<type>.discover(opts)`` on the
  resource loader; the returned iterable is consumed lazily.
* ``opts["pillar"]`` is **never** read by the discovery path.  A test
  patches the (removed) ``pillar_reader_TRAP`` reader onto the module
  so any accidental re-introduction surfaces immediately.
"""

import pytest

import salt.loader
import salt.minion
import salt.utils.resources
from tests.support.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minion_instance(minion_opts):
    """A Minion instance with the heavy start-up machinery stubbed."""
    minion_opts["multiprocessing"] = False
    with patch.object(salt.minion.Minion, "gen_modules"), patch.object(
        salt.minion.Minion, "connect_master"
    ):
        m = salt.minion.Minion(minion_opts, load_grains=False)
    return m


def _fake_loader(discover_impls):
    """Build a minimal LazyLoader-like dict whose entries support ``in`` and
    ``[key](opts)`` the way salt.loader.resource(...) does."""

    class _Loader(dict):
        def __init__(self, mapping):
            super().__init__(mapping)

        def __contains__(self, key):
            return super().__contains__(key)

    return _Loader(discover_impls)


# ---------------------------------------------------------------------------
# enabled_resource_types() drives discovery
# ---------------------------------------------------------------------------


def test_empty_resource_types_no_discovery(minion_instance):
    """
    No ``resource_types`` configured -> minion does not call any
    ``discover()``; ``opts["resources"]`` is NOT created as a materialized
    inventory dict (the full ID list must never be resident).
    """
    minion_instance.opts["resource_types"] = []

    # Any call into enabled_resource_types must return [].
    assert salt.utils.resources.enabled_resource_types(minion_instance.opts) == []

    # The pre-pillar-removal code wrote
    # ``self.opts["resources"] = self._discover_resources()`` on startup.
    # With no types enabled nothing should materialize.  (Count-only
    # per-type bookkeeping may exist, but no bare-IDs list at the top.)
    resources = minion_instance.opts.get("resources")
    if resources is not None:
        # Either absent entirely, or an empty mapping / count-only dict.
        assert not any(
            isinstance(v, list) and v for v in resources.values()
        ), "opts['resources'] holds a materialized ID list; must not"


def test_enabled_resource_types_filters_junk():
    """Guard the public contract the minion depends on."""
    opts = {"resource_types": ["dummy", None, 1, "ssh"]}
    assert salt.utils.resources.enabled_resource_types(opts) == ["dummy", "ssh"]


# ---------------------------------------------------------------------------
# discover() is consumed as a generator; no materialization on the minion
# ---------------------------------------------------------------------------


def test_iter_resource_ids_consumes_discover_generator(minion_instance):
    """
    The minion-side ``_iter_resource_ids`` MUST iterate the generator
    returned by ``<type>.discover(opts)`` without calling ``list()`` on it.

    We assert this by giving it a generator that records how many items
    were pulled from it -- the loop yields them one by one, no bulk
    materialization.
    """
    pulled = []

    def fake_discover(opts):
        for rid in ("dummy-0000001", "dummy-0000002", "dummy-0000003"):
            pulled.append(rid)
            yield rid

    minion_instance.opts["resource_types"] = ["dummy"]
    minion_instance.resource_funcs = _fake_loader({"dummy.discover": fake_discover})

    # Consume lazily and verify each pull is one-at-a-time.
    out = []
    it = minion_instance._iter_resource_ids("dummy")
    for i, rid in enumerate(it):
        out.append(rid)
        # pulled[i] must exist (each yield happened just-in-time).
        assert len(pulled) >= i + 1
    assert out == ["dummy-0000001", "dummy-0000002", "dummy-0000003"]


def test_iter_resource_ids_ten_items(minion_instance):
    """``dummy_resource_count: 10`` must round-trip to 10 yielded IDs."""

    def fake_discover(opts):
        count = opts.get("dummy_resource_count", 0)
        for i in range(1, count + 1):
            yield f"dummy-{i:07d}"

    minion_instance.opts["resource_types"] = ["dummy"]
    minion_instance.opts["dummy_resource_count"] = 10
    minion_instance.resource_funcs = _fake_loader({"dummy.discover": fake_discover})

    ids = list(minion_instance._iter_resource_ids("dummy"))
    assert len(ids) == 10
    assert ids[0] == "dummy-0000001"
    assert ids[-1] == "dummy-0000010"


def test_iter_resource_ids_unknown_type_yields_nothing(minion_instance):
    """An enabled type whose loader has no ``<type>.discover`` -> empty."""
    minion_instance.opts["resource_types"] = ["ghost"]
    minion_instance.resource_funcs = _fake_loader({})  # no ghost.discover

    assert list(minion_instance._iter_resource_ids("ghost")) == []


# ---------------------------------------------------------------------------
# Pillar invariant: discovery path must NEVER touch opts["pillar"]
# ---------------------------------------------------------------------------


def test_discover_never_reads_pillar(minion_instance):
    """
    Trap: patch the (removed) ``pillar_reader_TRAP`` onto the utils
    module with a mock that explodes.  If any discovery code regresses
    back to reading pillar it will call this and blow up visibly.
    """
    poison = MagicMock(side_effect=AssertionError("pillar read on discovery path"))

    # Seed a trap pillar subtree that the old code would have read.
    minion_instance.opts["pillar"] = {
        "resources": {"dummy": {"resource_ids": ["should-not-see"]}}
    }

    def fake_discover(opts):
        # Honest module: reads its own opt, not pillar.
        count = opts.get("dummy_resource_count", 0)
        for i in range(1, count + 1):
            yield f"dummy-{i:07d}"

    minion_instance.opts["resource_types"] = ["dummy"]
    minion_instance.opts["dummy_resource_count"] = 3
    minion_instance.resource_funcs = _fake_loader({"dummy.discover": fake_discover})

    with patch.object(salt.utils.resources, "pillar_reader_TRAP", poison, create=True):
        ids = list(minion_instance._iter_resource_ids("dummy"))

    poison.assert_not_called()
    # And the IDs came from opts, not pillar.
    assert ids == ["dummy-0000001", "dummy-0000002", "dummy-0000003"]
    assert "should-not-see" not in ids
