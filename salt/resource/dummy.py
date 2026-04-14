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
"""

import copy
import logging
import os
import pprint
from contextlib import contextmanager

import salt.utils.files
import salt.utils.msgpack
import salt.utils.resources

log = logging.getLogger(__name__)


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
    cachefile = os.path.join(opts["cachedir"], f"dummy-resource-{resource_id}.cache")
    with salt.utils.files.fopen(cachefile, "wb") as pck:
        pck.write(salt.utils.msgpack.packb(details, use_bin_type=True))
    log.warning(
        "Dummy Resource Saved State(%s):\n%s", cachefile, pprint.pformat(details)
    )


def _load_state(opts, resource_id):
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
    log.warning(
        "Dummy Resource Loaded State(%s):\n%s", cachefile, pprint.pformat(state)
    )
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
