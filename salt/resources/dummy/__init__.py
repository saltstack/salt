"""
Dummy resource module for testing the Salt resource subsystem.

This module implements the ``dummy`` resource type.  It is the resource
analogue of ``salt.proxy.dummy`` — a self-contained, file-backed
implementation that exercises the full resource lifecycle without requiring
any real managed devices.

Unlike a proxy module, a resource module is loaded **once per resource type
per minion**.  A single instance of this module handles all ``dummy``
resources managed by the minion.  The current resource context is conveyed
via the ``__resource__`` dunder rather than as a function parameter, keeping
the interface consistent with all other Salt module systems.

Configuration (via Pillar)::

    resources:
      dummy:
        resource_ids:
          - dummy-01
          - dummy-02
          - dummy-03

Scale-mode (in-memory state)
----------------------------

By default each per-resource state save/load round-trips through a cache
file at ``<cachedir>/dummy-resource-<resource_id>.cache``.  This is what
the original small-scale lifecycle tests rely on.

For large-scale testing (benchmarks, chunked-register scale tests,
repeated register runs) the per-resource filesystem I/O becomes the
bottleneck — a 200K-resource register across five minions generates on
the order of a million cache-file writes plus the associated log churn.

The minion opt ``dummy_resource_persist_state`` (default ``True``)
controls this behavior.  When set to ``False`` the module keeps state in
a bounded, process-local ``OrderedDict`` (LRU eviction) and performs no
filesystem I/O at all.  The size of that in-memory store is tunable via
``dummy_resource_state_max_entries`` (default 100000).

Tradeoff: in scale-mode there is **no persistence across minion
restarts**, and once the store reaches its max-entries cap the oldest
entries are evicted and will be re-initialized on next access.  That is
acceptable for scale testing (where the state round-trip is not what is
being measured) but is explicitly not what a correctness/lifecycle test
wants — leave the opt at its default in those cases.
"""

import copy
import logging
import os
import pprint
from collections import OrderedDict
from contextlib import contextmanager

import salt.utils.files
import salt.utils.msgpack
import salt.utils.resources

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-memory state store (scale-mode)
# ---------------------------------------------------------------------------
#
# When ``dummy_resource_persist_state`` is False the per-resource state dict
# lives here instead of in a cache file.  OrderedDict + move_to_end gives us
# cheap LRU semantics without pulling in a dependency.  The resource module
# is invoked serially from a single minion process, so no locking is needed.

_DEFAULT_MAX_ENTRIES = 100000
_memory_state = OrderedDict()


def _state_max_entries(opts):
    try:
        return int(opts.get("dummy_resource_state_max_entries", _DEFAULT_MAX_ENTRIES))
    except (TypeError, ValueError):
        return _DEFAULT_MAX_ENTRIES


def _persist_state(opts):
    """Return True when the default on-disk cache behavior is in effect."""
    return bool(opts.get("dummy_resource_persist_state", True))


def _memory_store_reset():
    """Clear the module-level in-memory state store (test helper)."""
    _memory_state.clear()


def __virtual__():
    """
    Always available — no external dependencies required.
    """
    log.debug("dummy resource __virtual__() called...")
    return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resource_id():
    """
    Return the ID of the resource currently being operated on.

    The execution layer sets ``__resource__`` before every per-resource
    dispatch.  All per-resource functions call this rather than accepting
    an ID parameter.
    """
    return __resource__["id"]  # pylint: disable=undefined-variable


def _initial_state(resource_id):
    return {
        "id": resource_id,
        "services": {"apache": "running", "ntp": "running", "samba": "stopped"},
        "packages": {
            "coreutils": "1.0",
            "apache": "2.4",
            "tinc": "1.4",
            "redbull": "999.99",
        },
    }


def _save_state(opts, resource_id, details):
    if not _persist_state(opts):
        # In-memory scale-mode: store a deep copy so callers can't mutate the
        # cache in place, and enforce LRU bounds.
        max_entries = _state_max_entries(opts)
        _memory_state[resource_id] = copy.deepcopy(details)
        _memory_state.move_to_end(resource_id)
        while len(_memory_state) > max_entries:
            _memory_state.popitem(last=False)
        log.debug(
            "Dummy Resource Saved State(memory:%s):\n%s",
            resource_id,
            pprint.pformat(details),
        )
        return
    cachefile = os.path.join(opts["cachedir"], f"dummy-resource-{resource_id}.cache")
    with salt.utils.files.fopen(cachefile, "wb") as pck:
        pck.write(salt.utils.msgpack.packb(details, use_bin_type=True))
    log.debug("Dummy Resource Saved State(%s):\n%s", cachefile, pprint.pformat(details))


def _load_state(opts, resource_id):
    if not _persist_state(opts):
        cached = _memory_state.get(resource_id)
        if cached is None:
            state = _initial_state(resource_id)
            _save_state(opts, resource_id, state)
        else:
            # Touch for LRU, return a fresh copy so the caller's mutations
            # don't retroactively edit the store.
            _memory_state.move_to_end(resource_id)
            state = copy.deepcopy(cached)
        log.debug(
            "Dummy Resource Loaded State(memory:%s):\n%s",
            resource_id,
            pprint.pformat(state),
        )
        return state
    cachefile = os.path.join(opts["cachedir"], f"dummy-resource-{resource_id}.cache")
    try:
        with salt.utils.files.fopen(cachefile, "rb") as pck:
            state = salt.utils.msgpack.unpackb(pck.read(), raw=False)
    except FileNotFoundError:
        state = _initial_state(resource_id)
        _save_state(opts, resource_id, state)
    except Exception as exc:  # pylint: disable=broad-except
        log.exception("Failed to load state: %s", exc, exc_info=True)
        state = _initial_state(resource_id)
        _save_state(opts, resource_id, state)
    log.debug("Dummy Resource Loaded State(%s):\n%s", cachefile, pprint.pformat(state))
    return state


@contextmanager
def _loaded_state(opts, resource_id):
    state = _load_state(opts, resource_id)
    original = copy.deepcopy(state)
    try:
        yield state
    finally:
        if state != original:
            _save_state(opts, resource_id, state)


# ---------------------------------------------------------------------------
# Required resource interface
# ---------------------------------------------------------------------------


def init(opts):
    """
    Initialize the dummy resource type for this minion.

    Called once when the resource type is loaded, before any per-resource
    operations are performed.  Reads the resource type configuration from the
    ``dummy`` entry under the pillar subtree selected by ``resource_pillar_key``
    (see :func:`salt.utils.resources.pillar_resources_tree`) and sets up shared type-level
    state in ``__context__["dummy_resource"]``.

    :param dict opts: The Salt opts dict.
    """
    resource_ids = (
        salt.utils.resources.pillar_resources_tree(opts)
        .get("dummy", {})
        .get("resource_ids", [])
    )
    __context__["dummy_resource"] = {
        "initialized": True,
        "resource_ids": resource_ids,
    }
    log.debug("dummy resource init() called, managing: %s", resource_ids)


def initialized():
    """
    Return ``True`` if ``init()`` has been called successfully for this
    resource type.

    Checked by the loader before dispatching per-resource operations, in the
    same way ``salt.proxy.dummy.initialized()`` is used today.

    :rtype: bool
    """
    return __context__.get("dummy_resource", {}).get("initialized", False)


def discover(opts):
    """
    Return the list of resource IDs of type ``dummy`` that this minion
    manages.

    Called by ``saltutil.refresh_resources`` to populate the master's
    Resource Registry.  For the dummy module the list of IDs is read from
    ``resource_ids`` under the ``dummy`` type in the configured resource pillar
    subtree.

    Returns a list of bare resource IDs (not full SRNs) — e.g.
    ``["dummy-01", "dummy-02"]``.

    :param dict opts: The Salt opts dict.
    :rtype: list[str]
    """
    resource_ids = (
        salt.utils.resources.pillar_resources_tree(opts)
        .get("dummy", {})
        .get("resource_ids", [])
    )
    log.debug("dummy resource discover() returning: %s", resource_ids)
    return resource_ids


def grains():
    """
    Return the grains dict for the current resource.

    The current resource context is available via ``__resource__``.  Each
    dummy resource reports a small set of static grains for use in targeting
    and state execution.

    :rtype: dict
    """
    resource_id = _resource_id()
    with _loaded_state(
        __opts__, resource_id
    ) as state:  # pylint: disable=undefined-variable
        state["grains_cache"] = {  # pylint: disable=unsupported-assignment-operation
            "dummy_grain_1": "one",
            "dummy_grain_2": "two",
            "dummy_grain_3": "three",
            "resource_id": resource_id,
        }
        return state["grains_cache"]


def grains_refresh():
    """
    Invalidate the cached grains for the current resource and return a
    freshly generated grains dict.

    :rtype: dict
    """
    resource_id = _resource_id()
    with _loaded_state(
        __opts__, resource_id
    ) as state:  # pylint: disable=undefined-variable
        state.pop("grains_cache", None)
    return grains()


def ping():
    """
    Return ``True`` if the current resource is reachable and responsive.

    For the dummy module this always returns ``True``; no real connection
    is made.
    """
    resource_id = _resource_id()
    log.debug("dummy resource ping() called for %s", resource_id)
    return True


def shutdown(opts):
    """
    Tear down the dummy resource type.

    Called when the minion shuts down or the resource type is unloaded.
    Cleans up shared type-level state from ``__context__``.

    :param dict opts: The Salt opts dict.
    """
    log.debug("dummy resource shutdown() called...")
    __context__.pop("dummy_resource", None)


# ---------------------------------------------------------------------------
# Per-resource operations (mirrors salt.proxy.dummy for testing parity)
# ---------------------------------------------------------------------------


def service_start(name):
    """
    Start a "service" on the current dummy resource.
    """
    with _loaded_state(
        __opts__, _resource_id()
    ) as state:  # pylint: disable=undefined-variable
        state["services"][name] = "running"
    return "running"


def service_stop(name):
    """
    Stop a "service" on the current dummy resource.
    """
    with _loaded_state(
        __opts__, _resource_id()
    ) as state:  # pylint: disable=undefined-variable
        state["services"][name] = "stopped"
    return "stopped"


def service_restart(name):
    """
    Restart a "service" on the current dummy resource.
    """
    return True


def service_list():
    """
    List "services" on the current dummy resource.
    """
    with _loaded_state(
        __opts__, _resource_id()
    ) as state:  # pylint: disable=undefined-variable
        return list(state["services"])


def service_status(name):
    """
    Return the status of a service on the current dummy resource.
    """
    with _loaded_state(
        __opts__, _resource_id()
    ) as state:  # pylint: disable=undefined-variable
        if state["services"][name] == "running":
            return {"comment": "running"}
        return {"comment": "stopped"}


def package_list():
    """
    List "packages" installed on the current dummy resource.
    """
    with _loaded_state(
        __opts__, _resource_id()
    ) as state:  # pylint: disable=undefined-variable
        return state["packages"]


def package_install(name, **kwargs):
    """
    Install a "package" on the current dummy resource.
    """
    version = kwargs.get("version", "1.0")
    with _loaded_state(
        __opts__, _resource_id()
    ) as state:  # pylint: disable=undefined-variable
        state["packages"][name] = version
    return {name: version}


def package_remove(name):
    """
    Remove a "package" from the current dummy resource.
    """
    with _loaded_state(
        __opts__, _resource_id()
    ) as state:  # pylint: disable=undefined-variable
        state["packages"].pop(name)
        return state["packages"]


def package_status(name):
    """
    Return the installation status of a package on the current dummy resource.
    """
    with _loaded_state(
        __opts__, _resource_id()
    ) as state:  # pylint: disable=undefined-variable
        if name in state["packages"]:
            return {name: state["packages"][name]}


def upgrade():
    """
    "Upgrade" all packages on the current dummy resource.
    """
    with _loaded_state(
        __opts__, _resource_id()
    ) as state:  # pylint: disable=undefined-variable
        for pkg in state["packages"]:
            state["packages"][pkg] = str(float(state["packages"][pkg]) + 1.0)
        return state["packages"]


def uptodate():
    """
    Report whether packages on the current dummy resource are up to date.
    """
    with _loaded_state(
        __opts__, _resource_id()
    ) as state:  # pylint: disable=undefined-variable
        return state["packages"]


def test_from_state():
    """
    Test function so we have something to call from a state.
    """
    log.debug("test_from_state called for resource %s", _resource_id())
    return "testvalue"
