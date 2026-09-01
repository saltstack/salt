"""
Unit tests for ``pkg/common/onedir/_salt_onedir_extras.py``.

This module is the ``.pth``-installed hook that prepends the salt-pip
extras directory to ``sys.path`` at interpreter startup. It runs before
salt itself is importable, so it lives outside the ``salt`` package.
"""

import importlib.util
import pathlib
import sys

import pytest

_EXTRAS_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[3]
    / "pkg"
    / "common"
    / "onedir"
    / "_salt_onedir_extras.py"
)


@pytest.fixture
def extras_module():
    """
    Load ``_salt_onedir_extras`` fresh from disk so each test starts with
    the sys.path shape the interpreter would present at startup.
    """
    spec = importlib.util.spec_from_file_location(
        "_salt_onedir_extras_under_test", _EXTRAS_MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _default_extras_path(pth_file_path):
    """Recompute the historical <relenv_root>/extras-<py> path."""
    parent = pathlib.Path(pth_file_path).resolve().parent.parent
    if not sys.platform.startswith("win"):
        parent = parent.parent
    return str(parent / "extras-{}.{}".format(*sys.version_info))


def test_setup_falls_back_to_relenv_extras(extras_module, monkeypatch, tmp_path):
    """
    Without SALT_EXTRAS_DIR set, the extras dir is derived from the
    ``.pth`` file's on-disk location (the historical behavior).
    """
    monkeypatch.delenv("SALT_EXTRAS_DIR", raising=False)
    pth_file = tmp_path / "sub1" / "sub2" / "sub3" / "_salt_onedir_extras.pth"
    pth_file.parent.mkdir(parents=True)
    pth_file.write_text("")

    expected = _default_extras_path(pth_file)

    original_path = list(sys.path)
    try:
        extras_module.setup(str(pth_file))
        assert sys.path[0] == expected
    finally:
        sys.path[:] = original_path


def test_setup_honors_env_override(extras_module, monkeypatch, tmp_path):
    """
    When SALT_EXTRAS_DIR is set, it wins over the .pth-derived path.
    This is the packaging hardened-layout path (issue #70198).
    """
    override = "/var/lib/salt/minion/extras-3.11"
    monkeypatch.setenv("SALT_EXTRAS_DIR", override)
    pth_file = tmp_path / "sub1" / "sub2" / "sub3" / "_salt_onedir_extras.pth"
    pth_file.parent.mkdir(parents=True)
    pth_file.write_text("")

    original_path = list(sys.path)
    try:
        extras_module.setup(str(pth_file))
        assert sys.path[0] == override
    finally:
        sys.path[:] = original_path


def test_setup_promotes_existing_path_entry(extras_module, monkeypatch, tmp_path):
    """
    If the extras path is already on sys.path but not at index 0, setup
    moves it to the front.
    """
    override = "/var/lib/salt/master/extras-3.11"
    monkeypatch.setenv("SALT_EXTRAS_DIR", override)
    pth_file = tmp_path / "_salt_onedir_extras.pth"
    pth_file.write_text("")

    original_path = list(sys.path)
    try:
        sys.path.append(override)
        extras_module.setup(str(pth_file))
        assert sys.path[0] == override
        # And is not duplicated.
        assert sys.path.count(override) == 1
    finally:
        sys.path[:] = original_path
