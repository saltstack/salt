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
from tests.support.mock import patch


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


@pytest.mark.parametrize("grains_value", ["", '""', "[]", "foo", "42", "[1, 2]"])
def test_grains_with_non_dict_grains_config_option(tmp_path, grains_value):
    """
    salt.loader.grains() re-reads the raw minion config file off disk to
    pick up any grains overrides. If 'grains:' is present in that file
    with a non-dict value (empty, a string, a number, a list, ...), that
    raw value must not be propagated into opts['grains'] as-is, or
    building the __grains__ NamespacedDictWrapper later crashes with
    "TypeError: 'NoneType' object is not iterable" or similar. See
    issue #61321.
    """
    conf_file = str(tmp_path / "minion")
    with salt.utils.files.fopen(conf_file, "w") as fp:
        fp.write(f"root_dir: {tmp_path}\ngrains: {grains_value}\n")
    opts = salt.config.minion_config(conf_file)
    grains = salt.loader.grains(opts, force_refresh=True)
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
        "optimization_order": [0],
    }
    ret = salt.loader.raw_mod(opts, "grains", "get")
    for k, v in ret.items():
        assert isinstance(v, salt.loader.lazy.LoadedFunc)


def test_named_loader_context_name_not_packed(tmp_path):
    opts = {
        "optimization_order": [0],
    }
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
