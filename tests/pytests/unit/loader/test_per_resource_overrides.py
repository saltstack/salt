"""
Unit tests for the per-type directory override mechanism introduced
for Gap 2 / Gap 4 / Gap 5, and for the deny-by-default surface of
:func:`salt.loader.resource_modules`.

The salt loader's :func:`_module_dirs` checks for
``resources/<rtype>/<ext_type>/`` subdirectories under every layer that
already contributes modules (``module_dirs``, ``extension_modules``,
entry-point packages, the in-tree salt package).  When found, the
per-type subdir is prepended before that layer's standard directory,
giving per-type overrides priority for that layer.

The per-resource execution loader built by :func:`resource_modules`
must expose **only** per-type override modules (from those overlay
dirs) plus the ``__minion__`` escape hatch.  Stock ``salt/modules/*``
must not be reachable via that loader — resource-context code that
needs the managing minion calls ``__minion__["module.fun"]`` explicitly.

These tests exercise the override mechanism end-to-end:

* A resource type that opts in via ``<extension_modules>/resources/<rtype>/modules/test.py``
  — its ``test.whoami`` is present and callable when the per-resource
  loader is built for that rtype.
* A resource type with no override — the resource loader is empty
  (no stock modules leak through).
* The ``__minion__`` dunder is packed into the per-resource execution
  loader when ``minion_mods`` is supplied — providing the escape-hatch
  back to the managing minion's loader.
"""

from __future__ import annotations

import os

import pytest

import salt.config
import salt.loader
import salt.utils.files


@pytest.fixture
def loader_opts(tmp_path):
    """A minimal opts dict pointing at tmp_path for ``extension_modules``."""
    extmods = tmp_path / "extmods"
    extmods.mkdir()
    opts = salt.config.minion_config(None)
    opts["root_dir"] = str(tmp_path)
    opts["cachedir"] = str(tmp_path / "cache")
    opts["pki_dir"] = str(tmp_path / "pki")
    opts["sock_dir"] = str(tmp_path / "run")
    opts["extension_modules"] = str(extmods)
    opts["file_client"] = "local"
    for d in (opts["cachedir"], opts["pki_dir"], opts["sock_dir"]):
        os.makedirs(d, exist_ok=True)
    return opts


def _drop_override(extmods, rtype, slot, body):
    """Place an override module at <extmods>/resources/<rtype>/modules/<slot>.py."""
    target = os.path.join(extmods, "resources", rtype, "modules")
    os.makedirs(target, exist_ok=True)
    path = os.path.join(target, f"{slot}.py")
    with salt.utils.files.fopen(path, "w") as f:
        f.write(body)
    return path


def test_per_type_dir_override_wins_over_standard(loader_opts):
    """
    A per-type override at <extmods>/resources/<rtype>/modules/<slot>.py
    must win over Salt's standard ``salt/modules/<slot>.py`` when the
    per-resource loader is built for that rtype.
    """
    body = "def whoami():\n    return 'override-wins'\n"
    _drop_override(loader_opts["extension_modules"], "ovrtest", "test", body)

    utils = salt.loader.utils(loader_opts)
    rfuncs = salt.loader.resource(loader_opts, utils=utils)
    loader = salt.loader.resource_modules(
        loader_opts, "ovrtest", resource_funcs=rfuncs, utils=utils
    )

    assert "test.whoami" in loader, sorted(
        k for k in loader.keys() if k.startswith("test.")
    )
    assert loader["test.whoami"]() == "override-wins"


def test_no_override_hides_stock_modules(loader_opts):
    """
    Resource type with no per-type overrides: the per-resource loader
    exposes NO stock ``salt/modules/*`` functions.  The documented
    Resources safety contract requires that ``salt <resource-id> cmd.run
    …`` / ``grains.setval …`` / ``state.sls …`` fail with "not supported
    for resource type" instead of silently executing on the managing
    minion.  The resource loader is the surface that decides this — if
    stock modules are present here, they will run.

    NOTE: this replaces an earlier test that asserted stock ``state.sls``
    was present in the resource loader.  That assertion documented the
    buggy behavior fixed by #69881; the contract restored here matches
    the resource-loader design (deny-by-default, type-local only).
    """
    utils = salt.loader.utils(loader_opts)
    rfuncs = salt.loader.resource(loader_opts, utils=utils)
    loader = salt.loader.resource_modules(
        loader_opts, "logical_test", resource_funcs=rfuncs, utils=utils
    )

    leaked = sorted(
        k
        for k in loader.keys()
        if k.split(".", 1)[0]
        in (
            "cmd",
            "state",
            "grains",
            "file",
            "system",
            "disk",
            "pkg",
            "service",
            "sys",
            "saltutil",
        )
    )
    assert not leaked, (
        "stock salt/modules leaked into the resource loader for a type "
        f"with no per-type overrides: {leaked[:20]}"
    )
    # Empty surface is the correct default for an inventory-only resource
    # type that ships no override modules.
    assert list(loader.keys()) == [], sorted(loader.keys())[:20]


def test_per_type_override_present_and_callable(loader_opts):
    """
    A per-type override at <extmods>/resources/<rtype>/modules/<slot>.py
    is present in the per-resource loader AND stock modules for the same
    resource-type surface are absent.  Confirms deny-by-default plus the
    per-type overlay together — the override is what the operator gets
    to invoke against the resource, nothing more.
    """
    body = "def ping():\n    return 'override-pong'\n"
    _drop_override(loader_opts["extension_modules"], "posovr", "test", body)

    utils = salt.loader.utils(loader_opts)
    rfuncs = salt.loader.resource(loader_opts, utils=utils)
    loader = salt.loader.resource_modules(
        loader_opts, "posovr", resource_funcs=rfuncs, utils=utils
    )

    assert "test.ping" in loader, sorted(
        k for k in loader.keys() if k.startswith("test.")
    )
    assert loader["test.ping"]() == "override-pong"

    # Only the override slot's functions are visible; no stock cmd/state/…
    leaked = sorted(
        k
        for k in loader.keys()
        if k.split(".", 1)[0]
        in ("cmd", "state", "grains", "file", "system", "sys", "saltutil")
    )
    assert not leaked, leaked[:20]


def test_minion_mods_packed_as_dunder(loader_opts):
    """
    When ``minion_mods=`` is supplied to ``resource_modules()``, the
    per-resource loader's pack carries it as ``__minion__`` so resource-
    specific modules can call back to the managing minion explicitly.
    """
    utils = salt.loader.utils(loader_opts)
    rfuncs = salt.loader.resource(loader_opts, utils=utils)
    minion = salt.loader.minion_mods(loader_opts, utils=utils)
    loader = salt.loader.resource_modules(
        loader_opts,
        "withescape",
        resource_funcs=rfuncs,
        utils=utils,
        minion_mods=minion,
    )
    assert "__minion__" in loader.pack
    assert loader.pack["__minion__"] is minion


def test_minion_mods_omitted_keeps_dunder_unset(loader_opts):
    """
    When ``minion_mods=`` is omitted, ``__minion__`` is not packed —
    keeping the dunder absent in legacy callers that don't set it.
    """
    utils = salt.loader.utils(loader_opts)
    rfuncs = salt.loader.resource(loader_opts, utils=utils)
    loader = salt.loader.resource_modules(
        loader_opts, "noescape", resource_funcs=rfuncs, utils=utils
    )
    assert "__minion__" not in loader.pack


def test_per_type_states_dir_picked_up_when_opts_resource_type_set(loader_opts):
    """
    The per-type ``states`` subdirectory under
    ``<extmods>/resources/<rtype>/states/`` is visible to
    ``salt.loader.states`` when ``opts["resource_type"]`` is set.
    Resource type authors can supply state-module overrides this way.
    """
    target = os.path.join(
        loader_opts["extension_modules"], "resources", "stest", "states"
    )
    os.makedirs(target, exist_ok=True)
    with salt.utils.files.fopen(os.path.join(target, "rtype_only.py"), "w") as f:
        f.write(
            "def present(name):\n"
            "    return {'name': name, 'result': True, 'comment': 'ok',"
            " 'changes': {}}\n"
        )

    rtype_opts = dict(loader_opts)
    rtype_opts["resource_type"] = "stest"

    utils = salt.loader.utils(rtype_opts)
    serializers = salt.loader.serializers(rtype_opts)
    minion = salt.loader.minion_mods(rtype_opts, utils=utils)
    states = salt.loader.states(
        rtype_opts,
        functions=minion,
        utils=utils,
        serializers=serializers,
    )
    assert "rtype_only.present" in states, sorted(
        k for k in states.keys() if "rtype_only" in k
    )
