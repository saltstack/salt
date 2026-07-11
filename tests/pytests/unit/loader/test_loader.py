"""
tests.pytests.unit.loader.test_loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for salt's loader
"""

import os
import pathlib
import shutil
import sys
import textwrap

import pytest

import salt.config
import salt.exceptions
import salt.loader
import salt.loader.lazy
import salt.utils.files
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


def test_loader_does_not_shadow_top_level_import(tmp_path):
    """
    Loading a Salt-internal module must not put its directory on sys.path.

    Otherwise a same-named single-file Salt module (e.g. salt/utils/ssh.py)
    shadows a real top-level third-party package that a loaded module's import
    chain pulls in, and the shadow is cached in sys.modules for the life of the
    process. This is the root cause behind #69139: ncclient's bare ``import
    ssh`` (to detect ssh-python, which is normally not installed) bound to
    salt/utils/ssh.py, which broke ``import napalm``.
    """
    # Fake SALT_BASE_PATH tree. ``shadowmod`` stands in for salt/utils/ssh.py:
    # a plain single-file Salt module whose stem matches a top-level package a
    # loaded module's import chain would probe for. ``importer`` stands in for
    # salt.utils.napalm doing a bare third-party import while its body runs.
    # There is no real ``shadowmod`` package installed (as ssh-python normally
    # is not), so the only way ``import shadowmod`` can resolve is if the loader
    # leaks the Salt-internal dir onto sys.path.
    salt_root = tmp_path / "saltroot"
    loaderdir = salt_root / "mymods"
    loaderdir.mkdir(parents=True)
    (loaderdir / "shadowmod.py").write_text("MARKER = 'salt-internal-shadow'\n")
    (loaderdir / "importer.py").write_text(
        "try:\n"
        "    import shadowmod\n"
        "    RESULT = getattr(shadowmod, 'MARKER', 'other')\n"
        "except ImportError:\n"
        "    RESULT = 'not-importable'\n\n\n"
        "def result():\n"
        "    return RESULT\n"
    )

    opts = {"optimization_order": [0]}
    saved_path = list(sys.path)
    try:
        with patch.object(
            salt.loader.lazy, "SALT_BASE_PATH", pathlib.Path(str(salt_root))
        ):
            loader = salt.loader.LazyLoader([str(loaderdir)], opts)
            # With the fix, loaderdir (under SALT_BASE_PATH) is never appended to
            # sys.path, so a bare ``import shadowmod`` from another loaded module
            # cannot bind to loaderdir/shadowmod.py. Without the fix, loaderdir
            # is appended and the bare import binds to the Salt-internal file.
            assert loader["importer.result"]() == "not-importable"
    finally:
        sys.path[:] = saved_path
        sys.modules.pop("shadowmod", None)


def test_loader_self_named_module_not_self_shadowed_when_dep_absent(tmp_path):
    """
    A module named after its optional third-party dependency must not "load" by
    importing itself when that dependency is absent.

    This is the ethtool / dson / json5 class (32 salt modules bare-import their
    own name). salt/modules/ethtool.py does ``import ethtool``; with the
    module's own directory on sys.path that bound to the salt file itself, so
    the module falsely "loaded" while being self-referential and non-functional
    at runtime. With this fix it correctly does not load.
    """
    salt_root = tmp_path / "saltroot"
    loaderdir = salt_root / "mymods"
    loaderdir.mkdir(parents=True)
    # No real "widget" package is installed, mirroring an absent optional dep.
    (loaderdir / "widget.py").write_text(
        "import widget\n\n\ndef ok():\n    return getattr(widget, 'REAL', 'self')\n"
    )
    opts = {"optimization_order": [0]}
    saved_path = list(sys.path)
    try:
        with patch.object(
            salt.loader.lazy, "SALT_BASE_PATH", pathlib.Path(str(salt_root))
        ):
            loader = salt.loader.LazyLoader([str(loaderdir)], opts)
            # With the fix loaderdir is not on sys.path, so ``import widget``
            # raises ImportError and widget.py does not load. Without the fix it
            # self-imports and widget.ok shows up in the loader.
            assert "widget.ok" not in loader
    finally:
        sys.path[:] = saved_path
        sys.modules.pop("widget", None)


def test_loader_self_named_module_loads_via_real_dep_when_present(tmp_path):
    """
    Companion to the above: when the real same-named dependency IS installed,
    the module must still load and bind to the real package (not the salt file).
    Confirms the fix does not break these modules in the normal case.
    """
    # A real external "widget" package -- stands in for the installed dependency.
    site = tmp_path / "site"
    (site / "widget").mkdir(parents=True)
    (site / "widget" / "__init__.py").write_text("REAL = 'real-widget'\n")

    salt_root = tmp_path / "saltroot"
    loaderdir = salt_root / "mymods"
    loaderdir.mkdir(parents=True)
    (loaderdir / "widget.py").write_text(
        "import widget\n\n\ndef ok():\n    return getattr(widget, 'REAL', 'self')\n"
    )
    opts = {"optimization_order": [0]}
    saved_path = list(sys.path)
    sys.path.insert(0, str(site))
    try:
        with patch.object(
            salt.loader.lazy, "SALT_BASE_PATH", pathlib.Path(str(salt_root))
        ):
            loader = salt.loader.LazyLoader([str(loaderdir)], opts)
            assert loader["widget.ok"]() == "real-widget"
    finally:
        sys.path[:] = saved_path
        sys.modules.pop("widget", None)


def test_loader_external_module_dir_still_on_sys_path(tmp_path):
    """
    External (custom) module dirs must still be added to sys.path so a custom
    module's bare sibling import keeps resolving -- the fix only excludes
    Salt-internal dirs.
    """
    extdir = tmp_path / "ext"
    extdir.mkdir()
    (extdir / "sibling.py").write_text("VALUE = 'sib'\n")
    (extdir / "usesibling.py").write_text(
        "import sibling\n\n\ndef ok():\n    return sibling.VALUE\n"
    )
    opts = {"optimization_order": [0]}
    try:
        # extdir is not under the real SALT_BASE_PATH, so it is appended and the
        # bare ``import sibling`` resolves.
        loader = salt.loader.LazyLoader([str(extdir)], opts)
        assert loader["usesibling.ok"]() == "sib"
    finally:
        sys.modules.pop("sibling", None)


def test_loader_external_dir_sharing_salt_prefix_still_appended(tmp_path):
    """
    A module directory whose path merely *begins* with the Salt install path --
    e.g. a ``saltext.*`` extension installed sibling to the ``salt`` package in
    site-packages (``.../site-packages/saltext/...`` vs ``.../site-packages/salt``)
    -- must still be added to sys.path. A raw ``startswith`` guard would
    misclassify it as internal because "saltext" starts with "salt"; the fix
    uses a path-component boundary instead.
    """
    salt_root = tmp_path / "saltroot"
    salt_root.mkdir()
    # External dir that shares the "saltroot" textual prefix but is NOT under it.
    extdir = tmp_path / "saltroot_ext"
    extdir.mkdir()
    assert str(extdir).startswith(str(salt_root))  # the boundary condition
    (extdir / "sibling.py").write_text("VALUE = 'sib'\n")
    (extdir / "usesibling.py").write_text(
        "import sibling\n\n\ndef ok():\n    return sibling.VALUE\n"
    )
    opts = {"optimization_order": [0]}
    try:
        with patch.object(
            salt.loader.lazy, "SALT_BASE_PATH", pathlib.Path(str(salt_root))
        ):
            loader = salt.loader.LazyLoader([str(extdir)], opts)
            # extdir is a sibling of salt_root, not under it, so it must be
            # appended and the bare sibling import must resolve.
            assert loader["usesibling.ok"]() == "sib"
    finally:
        sys.modules.pop("sibling", None)
