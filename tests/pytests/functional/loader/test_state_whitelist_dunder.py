"""
Functional tests for the ``whitelist_modules`` two-loader propagation
into ``salt.loader.states`` and the Jinja attribute-style escape hatch
closure in ``salt.loader.lazy.LazyLoader.__getattr__`` /
``salt.utils.templates.AliasedLoader.__getattr__``.

These tests wire up real loaders (no mocks) but stop short of a full
salt-master + salt-minion pair, which is the integration tier.

Companion to :mod:`tests.pytests.integration.loader.test_module_whitelist_dunder`.
"""

import pytest

import salt.loader
import salt.loader.context
from salt.utils.templates import AliasedLoader


@pytest.fixture
def wl_opts(minion_opts):
    """Minion opts with a narrow ``whitelist_modules`` -- ``cmd`` deliberately absent."""
    opts = minion_opts.copy()
    opts["whitelist_modules"] = [
        "test",
        "grains",
        "state",
        "saltutil",
        "config",
        "pillar",
        "slsutil",
        "file",  # so ``file.managed`` can be *declared* in an SLS
    ]
    return opts


@pytest.fixture
def wl_loaders(wl_opts):
    """Build the outer wire-filtered loader and the states loader wired for the fix."""
    minion_mods = salt.loader.minion_mods(wl_opts)
    dunder_salt = getattr(minion_mods, "_dunder_salt", None)
    assert dunder_salt is not None, "PR #69983 two-loader model not present"
    utils = salt.loader.utils(wl_opts)
    serializers = salt.loader.serializers(wl_opts)
    states = salt.loader.states(
        wl_opts,
        minion_mods,
        utils,
        serializers,
        dunder_salt=dunder_salt,
    )
    return {
        "opts": wl_opts,
        "minion_mods": minion_mods,
        "dunder_salt": dunder_salt,
        "utils": utils,
        "states": states,
    }


# ---------------------------------------------------------------------------
# State-loader two-loader propagation
# ---------------------------------------------------------------------------


def test_state_loader_packs_unfiltered_salt(wl_loaders):
    """
    Every state module's packed ``__salt__`` is the *unfiltered* inner
    loader, so trusted shipped state code can compose with non-whitelisted
    exec modules (e.g. ``file.managed`` -> ``__salt__['file.source_list']``).
    """
    states = wl_loaders["states"]
    dunder_salt = wl_loaders["dunder_salt"]
    minion_mods = wl_loaders["minion_mods"]
    assert states.pack["__salt__"] is dunder_salt
    # ...and the wire loader is exposed as ``__wire_salt__`` for the few
    # state modules that legitimately dispatch an SLS-supplied name.
    assert states.pack["__wire_salt__"] is minion_mods
    # cmd isn't on the whitelist:
    assert "cmd.run" not in minion_mods
    # ...but the unfiltered dunder still has it:
    assert "cmd.run" in dunder_salt


def test_wire_loader_still_gates_cmd_run(wl_loaders):
    """The wire-facing loader must still refuse ``cmd.run``."""
    minion_mods = wl_loaders["minion_mods"]
    with pytest.raises(KeyError):
        _ = minion_mods["cmd.run"]


def test_trusted_state_module_can_reach_unfiltered_exec(wl_loaders):
    """
    Load ``file`` state and confirm its packed ``__salt__`` resolves the
    non-whitelisted ``file.source_list`` -- the exact function whose lookup
    used to raise ``KeyError`` when a template state ran under a strict
    whitelist.
    """
    states = wl_loaders["states"]
    # Force-load salt.states.file so its module-globals get populated.
    states._load_module("file")
    file_globals = states._dict["file.managed"].__globals__
    packed_salt = file_globals["__salt__"]
    # The pack surfaces as a ``NamedLoaderContext``; ``in`` delegates to
    # ``value()`` which needs an active loader context.
    token = salt.loader.context.loader_ctxvar.set(states)
    try:
        # ``file.source_list`` is on ``salt/modules/file.py`` which is NOT
        # on the whitelist -- but the trusted state's ``__salt__`` is the
        # unfiltered dunder, so the lookup succeeds.
        assert "file.source_list" in packed_salt
    finally:
        salt.loader.context.loader_ctxvar.reset(token)


# ---------------------------------------------------------------------------
# Jinja attribute-style escape hatch closure
# ---------------------------------------------------------------------------


def test_attr_style_whitelisted_resolves(wl_loaders):
    """``salt.grains`` for a whitelisted module returns a LoadedMod proxy."""
    al = AliasedLoader(wl_loaders["minion_mods"])
    assert hasattr(al, "grains")
    assert callable(al.grains.get)


def test_attr_style_non_whitelisted_raises_attribute_error(wl_loaders):
    """
    ``salt.cmd`` for a non-whitelisted module must raise ``AttributeError``
    so ``hasattr(salt, 'cmd')`` is False and Jinja's ``undefined``
    fallthrough behaves.  This closes the pre-existing attribute-style
    escape hatch in ``LazyLoader.__getattr__``.
    """
    al = AliasedLoader(wl_loaders["minion_mods"])
    with pytest.raises(AttributeError):
        _ = al.cmd
    assert not hasattr(al, "cmd")
    # And the same holds on the raw LazyLoader (AliasedLoader delegates
    # but the LazyLoader-level gate is authoritative).
    with pytest.raises(AttributeError):
        _ = wl_loaders["minion_mods"].cmd


def test_dict_style_still_gated(wl_loaders):
    """
    Sanity: dict-style access on both the raw loader and AliasedLoader
    stays whitelist-gated (the pre-fix behavior must not regress).
    """
    al = AliasedLoader(wl_loaders["minion_mods"])
    assert callable(al["test.ping"])
    with pytest.raises(KeyError):
        _ = al["cmd.run"]


# ---------------------------------------------------------------------------
# ``salt.states.module.run`` escape closure via ``__wire_salt__``
# ---------------------------------------------------------------------------


def test_state_engine_compiles_without_config_on_whitelist(wl_opts, tmp_path):
    """
    VCOPS-90587 round 3: ``compile_high_data`` reads
    ``config.option('state_aggregate')`` via the state engine.  Under a
    strict whitelist that omits ``config``, the pre-round-3 code
    KeyError'd at ``salt/state.py:1755``.  With
    ``_trusted_functions`` in place, the compile succeeds and returns
    the low chunks even when neither ``config`` nor ``file`` is on the
    wire whitelist.
    """
    import salt.state

    # Strip ``config`` so the wire loader can't resolve ``config.option``.
    opts = wl_opts.copy()
    opts["whitelist_modules"] = [m for m in opts["whitelist_modules"] if m != "config"]
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    st = salt.state.State(opts)
    # Confirm the wire loader is properly gated.
    assert "config.option" not in st.functions
    # A minimal high-data structure that exercises compile_high_data.
    high = {
        "example_id": {
            "test": [{"name": "example"}, "succeed_without_changes"],
            "__sls__": "example",
            "__env__": "base",
        }
    }
    chunks, errors = st.compile_high_data(high)
    assert errors == []
    assert isinstance(chunks, list)
    assert len(chunks) == 1
    assert chunks[0]["state"] == "test"


def test_states_module_helper_routes_through_wire_salt(wl_loaders):
    """
    ``salt.states.module._wire_salt()`` must return the wire-filtered
    loader so ``module.run``'s SLS-directed dispatch stays gated even
    though the surrounding state module has an unfiltered ``__salt__``.
    """
    states = wl_loaders["states"]
    states._load_module("module")
    module_globals = states._dict["module.run"].__globals__
    token = salt.loader.context.loader_ctxvar.set(states)
    try:
        wire_salt = module_globals["_wire_salt"]()
        # NamedLoaderContext binding under the loader; unwrap.
        if hasattr(wire_salt, "value"):
            wire_salt = wire_salt.value()
        assert wire_salt is wl_loaders["minion_mods"]
        assert "cmd.run" not in wire_salt
    finally:
        salt.loader.context.loader_ctxvar.reset(token)
