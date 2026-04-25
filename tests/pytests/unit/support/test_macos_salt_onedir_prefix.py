"""
Unit tests for macOS Salt install path probing in ``tests.support.pkg``.
"""

import pathlib

from tests.support import pkg


def test_macos_onedir_prefers_saltstack_bin_salt(monkeypatch):
    def exists(self):
        s = str(self).replace("\\", "/")
        if s.endswith("/opt/saltstack/salt/bin/salt"):
            return True
        return False

    monkeypatch.setattr(pathlib.Path, "exists", exists)
    assert pkg._macos_salt_onedir_prefix() == pathlib.Path("/opt/saltstack/salt")


def test_macos_onedir_opt_salt_flat_salt_wrapper(monkeypatch):
    def exists(self):
        s = str(self).replace("\\", "/")
        if s.endswith("/opt/saltstack/salt/bin/salt"):
            return False
        if s.endswith("/opt/salt/bin/salt"):
            return False
        if s.endswith("/opt/salt/salt"):
            return True
        return False

    monkeypatch.setattr(pathlib.Path, "exists", exists)
    assert pkg._macos_salt_onedir_prefix() == pathlib.Path("/opt/salt")


def test_macos_onedir_falls_back_to_opt_salt_bin_salt(monkeypatch):
    def exists(self):
        s = str(self).replace("\\", "/")
        if s.endswith("/opt/saltstack/salt/bin/salt"):
            return False
        if s.endswith("/opt/salt/bin/salt"):
            return True
        return False

    monkeypatch.setattr(pathlib.Path, "exists", exists)
    assert pkg._macos_salt_onedir_prefix() == pathlib.Path("/opt/salt")


def test_macos_onedir_which_fallback(monkeypatch):
    monkeypatch.setattr(pathlib.Path, "exists", lambda self: False)

    def fake_which(cmd, path=None, mode=None):
        if cmd == "salt":
            return "/opt/saltstack/salt/bin/salt"
        return None

    monkeypatch.setattr(pkg.shutil, "which", fake_which)
    assert pkg._macos_salt_onedir_prefix() == pathlib.Path("/opt/saltstack/salt")


def test_macos_onedir_which_ignores_non_opt(monkeypatch):
    monkeypatch.setattr(pathlib.Path, "exists", lambda self: False)

    def fake_which(cmd, path=None, mode=None):
        if cmd == "salt":
            return "/usr/local/bin/salt"
        return None

    monkeypatch.setattr(pkg.shutil, "which", fake_which)
    assert pkg._macos_salt_onedir_prefix() is None
