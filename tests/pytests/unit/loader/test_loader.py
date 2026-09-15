"""
tests.pytests.unit.loader.test_loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for salt's loader
"""

import os
import shutil
import textwrap

import pytest

import salt.config
import salt.exceptions
import salt.loader
import salt.loader.lazy
from tests.support.mock import MagicMock, patch


@pytest.fixture
def grains_dir(tmp_path):
    """
    Create a simple directory with grain modules.
    """
    grain_with_annotation = textwrap.dedent(
        """
        from typing import Dict

        def example_grain() -> Dict[str, str]:
            return {"example": "42"}
        """
    )
    tmp_path = str(tmp_path)
    with salt.utils.files.fopen(os.path.join(tmp_path, "example.py"), "w") as fp:
        fp.write(grain_with_annotation)
    try:
        yield tmp_path
    finally:
        shutil.rmtree(tmp_path)


def test_grains(minion_opts):
    """
    Load grains.
    """
    grains = salt.loader.grains(minion_opts, force_refresh=True)
    assert "saltversion" in grains


def test_custom_grain_with_annotations(minion_opts, grains_dir):
    """
    Load custom grain with annotations.
    """
    minion_opts["grains_dirs"] = [grains_dir]
    grains = salt.loader.grains(minion_opts, force_refresh=True)
    assert grains.get("example") == "42"


def test_raw_mod_functions():
    "Ensure functions loaded by raw_mod are LoaderFunc instances"
    opts = {
        "extension_modules": "",
    }
    ret = salt.loader.raw_mod(opts, "grains", "get")
    for k, v in ret.items():
        assert isinstance(v, salt.loader.lazy.LoadedFunc)


def test_named_loader_context_name_not_packed(tmp_path):
    opts = {}
    contents = """
    from salt.loader.dunder import loader_context
    __not_packed__ = loader_context.named_context("__not_packed__")
    def foobar():
        return __not_packed__["not.packed"]()
    """
    with pytest.helpers.temp_file("mymod.py", contents, directory=tmp_path):
        loader = salt.loader.LazyLoader([tmp_path], opts)
        with pytest.raises(
            salt.exceptions.LoaderError,
            match="LazyLoader does not have a packed value for: __not_packed__",
        ):
            loader["mymod.foobar"]()


def test_return_named_context_from_loaded_func(tmp_path):
    opts = {
        "optimization_order": [0],
    }
    contents = """
    def foobar():
        return __test__
    """
    with pytest.helpers.temp_file("mymod.py", contents, directory=tmp_path):
        loader = salt.loader.LazyLoader([tmp_path], opts, pack={"__test__": "meh"})
        assert loader["mymod.foobar"]() == "meh"


def test_render():
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    minion_mods = salt.loader.minion_mods(opts)
    for role in ["minion", "master"]:
        opts["__role"] = role
        for renderer in ["jinja|yaml", "some_custom_thing"]:
            opts["renderer"] = renderer
            ret = salt.loader.render(opts, minion_mods)
            assert isinstance(ret, salt.loader.lazy.FilterDictWrapper)
    with pytest.raises(salt.exceptions.LoaderError), patch(
        "salt.loader.check_render_pipe_str", MagicMock(side_effect=[False, False])
    ):
        salt.loader.render(opts, minion_mods)


# ---------------------------------------------------------------------------
# VCOPS-90587: state loader inherits ``whitelist_modules`` two-loader model
# ---------------------------------------------------------------------------


def _minion_opts_with_whitelist(minion_opts, whitelist):
    """Return a copy of ``minion_opts`` with ``whitelist_modules`` set."""
    opts = minion_opts.copy()
    opts["whitelist_modules"] = list(whitelist)
    return opts


def test_lazyloader_getattr_respects_whitelist(minion_opts):
    """
    VCOPS-90587 follow-up: ``LazyLoader.__getattr__`` must consult
    ``self.whitelist`` and raise ``AttributeError`` for non-whitelisted
    modules, so Jinja's attribute-style ``salt.cmd.run(...)`` binding
    can't sidestep ``whitelist_modules`` the way dict-style already can't.
    """
    opts = _minion_opts_with_whitelist(minion_opts, ["test", "grains"])
    ret = salt.loader.minion_mods(opts)
    # Whitelisted module resolves to a LoadedMod proxy.
    assert hasattr(ret, "test")
    # Non-whitelisted attribute access raises AttributeError.
    with pytest.raises(AttributeError):
        _unused = ret.cmd
    assert not hasattr(ret, "cmd")
    # Inner unfiltered dunder is not gated (trusted composition path).
    assert hasattr(ret._dunder_salt, "cmd")


def test_minion_mods_exposes_unfiltered_dunder_salt(minion_opts):
    """
    ``minion_mods`` builds a two-loader model when ``whitelist_modules`` is
    set (outer wire-filtered ``ret`` + inner unfiltered ``salt_dunder``).
    The inner loader must be exposed on the outer via ``_dunder_salt`` so
    downstream loader factories can pack it as their own ``__salt__``.
    """
    opts = _minion_opts_with_whitelist(minion_opts, ["test"])
    ret = salt.loader.minion_mods(opts)
    assert hasattr(ret, "_dunder_salt"), "outer loader missing _dunder_salt"
    salt_dunder = ret._dunder_salt
    assert salt_dunder is not ret
    # wire-facing loader is whitelist-gated ...
    assert "cmd.run" not in ret
    # ... but the inner dunder is not.
    assert "cmd.run" in salt_dunder


def test_states_loader_dunder_salt_passthrough(minion_opts):
    """
    When ``salt.loader.states`` is built with ``dunder_salt=<inner loader>``,
    the loaded state modules see the unfiltered loader as ``__salt__`` and
    the wire-filtered loader as ``__wire_salt__``.
    """
    opts = _minion_opts_with_whitelist(minion_opts, ["test", "file"])
    ret = salt.loader.minion_mods(opts)
    salt_dunder = ret._dunder_salt
    states = salt.loader.states(
        opts,
        ret,
        utils=None,
        serializers=None,
        dunder_salt=salt_dunder,
    )
    # The state loader packs both dunders; wire loader stays whitelist-gated,
    # __salt__ is the unfiltered inner loader.
    assert states.pack["__salt__"] is salt_dunder
    assert states.pack["__wire_salt__"] is ret
    # Trusted composition works: file.managed's ``__salt__`` reaches a
    # non-whitelisted exec module.
    assert "cmd.run" in states.pack["__salt__"]
    # Wire dispatch stays gated.
    assert "cmd.run" not in states.pack["__wire_salt__"]


def test_states_loader_backcompat_without_dunder_salt(minion_opts):
    """
    When ``dunder_salt`` is not supplied, ``salt.loader.states`` falls back
    to using ``functions`` as ``__salt__`` (pre-fix behaviour) so external
    callers -- including the master-side ``BaseHighState`` compile path --
    are not broken.
    """
    opts = _minion_opts_with_whitelist(minion_opts, ["test", "file"])
    ret = salt.loader.minion_mods(opts)
    states = salt.loader.states(opts, ret, utils=None, serializers=None)
    assert states.pack["__salt__"] is ret
    # __wire_salt__ still equals the wire loader in either mode.
    assert states.pack["__wire_salt__"] is ret


def test_states_module_run_uses_wire_salt(minion_opts):
    """
    ``salt.states.module.run`` must resolve SLS-directed function names
    against the wire-filtered loader so ``whitelist_modules`` continues to
    gate the escape-hatch path even though the surrounding state module now
    has an unfiltered ``__salt__``.
    """
    opts = _minion_opts_with_whitelist(minion_opts, ["test", "module"])
    ret = salt.loader.minion_mods(opts)
    salt_dunder = ret._dunder_salt
    states = salt.loader.states(
        opts, ret, utils=None, serializers=None, dunder_salt=salt_dunder
    )
    # Force-load module.py so its module-globals are wired.
    assert states.pack["__salt__"] is salt_dunder
    assert states.pack["__wire_salt__"] is ret
    # Sanity: cmd.run isn't on the whitelist, so wire_salt must miss it and
    # salt_dunder must have it.
    assert "cmd.run" not in ret
    assert "cmd.run" in salt_dunder
    # _wire_salt() returns the wire-filtered loader when __wire_salt__ is
    # packed by the loader.  Force-load module.py, activate the loader
    # context so the NamedLoaderContext binding resolves, and call the
    # (private) helper via the module globals of any function in the
    # loaded state module.
    import salt.loader.context as _lc

    states._load_module("module")
    module_globals = states._dict["module.run"].__globals__
    token = _lc.loader_ctxvar.set(states)
    try:
        wire_salt = module_globals["_wire_salt"]()
        # NamedLoaderContext under the loader; unwrap to the concrete loader.
        if hasattr(wire_salt, "value"):
            wire_salt = wire_salt.value()
    finally:
        _lc.loader_ctxvar.reset(token)
    assert wire_salt is ret
    assert "cmd.run" not in wire_salt


def test_state_trusted_functions_bypasses_whitelist(minion_opts, tmp_path):
    """
    VCOPS-90587 round 3: ``salt.state.State._trusted_functions`` must be
    the unfiltered inner exec-module loader so trusted state-engine
    internal call sites (``config.option``, ``state_aggregate``,
    ``saltutil.refresh_modules``, ``event.fire_master``, ``test.sleep``)
    keep working even when ``whitelist_modules`` excludes the modules
    they need.  ``self.functions`` stays wire-filtered for user-facing
    dispatch (``unless``/``onlyif``, slots, ``module.run``, Jinja).
    """
    import salt.state

    opts = _minion_opts_with_whitelist(minion_opts, ["test", "state"])
    opts["file_client"] = "local"
    opts["cachedir"] = str(tmp_path)
    st = salt.state.State(opts)
    # ``config`` is NOT on the whitelist, so ``self.functions`` (wire) rejects
    # it, but ``self._trusted_functions`` (unfiltered) still resolves it.
    assert "config.option" not in st.functions
    assert "config.option" in st._trusted_functions
    # And an actual invocation via the trusted route must succeed
    # (returns whatever the option evaluates to, including None/False).
    st._trusted_functions["config.option"]("state_aggregate")
