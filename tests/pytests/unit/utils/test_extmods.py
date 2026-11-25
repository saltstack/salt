"""
Tests for salt.utils.extmods
"""

import logging
import os

import pytest

import salt.utils.extmods
import salt.utils.files
from tests.support.mock import patch

pytestmark = [
    pytest.mark.core_test,
]


@pytest.fixture
def sync_opts(minion_opts, tmp_path):
    grains_dir = tmp_path / "srv" / "_grains"
    grains_dir.mkdir(parents=True)
    (grains_dir / "wanted.py").write_text("def main():\n    return {}\n")
    minion_opts.update(
        {
            "file_client": "local",
            "file_roots": {"base": [str(tmp_path / "srv")]},
            "fileserver_backend": ["roots"],
            "cachedir": str(tmp_path / "cache"),
            "extension_modules": str(tmp_path / "extmods"),
            "clean_dynamic_modules": True,
        }
    )
    stale = tmp_path / "extmods" / "grains"
    stale.mkdir(parents=True)
    (stale / "stale.py").write_text("def main():\n    return {}\n")
    return minion_opts


def test_sync_cleans_unlisted_modules_by_default(sync_opts, tmp_path):
    """
    With ``clean_dynamic_modules`` enabled, modules that are not in the file
    roots are removed.
    """
    ret, touched = salt.utils.extmods.sync(sync_opts, "grains", saltenv=["base"])
    assert ret == ["grains.wanted"]
    assert touched is True
    assert (tmp_path / "extmods" / "grains" / "wanted.py").is_file()
    assert not (tmp_path / "extmods" / "grains" / "stale.py").exists()


def test_sync_clean_false_keeps_unlisted_modules(sync_opts, tmp_path):
    """
    ``clean=False`` adds and updates modules but never removes any, whatever
    ``clean_dynamic_modules`` says.
    """
    ret, touched = salt.utils.extmods.sync(
        sync_opts, "grains", saltenv=["base"], clean=False
    )
    assert ret == ["grains.wanted"]
    assert touched is True
    assert (tmp_path / "extmods" / "grains" / "wanted.py").is_file()
    assert (tmp_path / "extmods" / "grains" / "stale.py").is_file()


def test_sync_clean_true_overrides_opts(sync_opts, tmp_path):
    sync_opts["clean_dynamic_modules"] = False
    salt.utils.extmods.sync(sync_opts, "grains", saltenv=["base"], clean=True)
    assert not (tmp_path / "extmods" / "grains" / "stale.py").exists()


@pytest.fixture
def cachedir(tmp_path):
    path = tmp_path / "cache"
    path.mkdir()
    return str(path)


@pytest.fixture
def extension_modules(tmp_path):
    return str(tmp_path / "extmods")


@pytest.fixture
def opts(cachedir, extension_modules):
    return {
        "cachedir": cachedir,
        "extension_modules": extension_modules,
        "extmod_whitelist": {},
        "extmod_blacklist": {},
        "clean_dynamic_modules": True,
        "hash_type": "sha256",
    }


@pytest.fixture
def fileclient(cachedir):
    """
    Serve ``_modules/foo.py`` with different contents per saltenv, the way a
    gitfs master with a ``qa`` branch and a ``master`` branch would.
    """
    contents = {"base": "VERSION = '1.0'\n", "qa": "VERSION = '1.1'\n"}
    for saltenv, body in contents.items():
        env_dir = os.path.join(cachedir, "files", saltenv, "_modules")
        os.makedirs(env_dir)
        with salt.utils.files.fopen(
            os.path.join(env_dir, "foo.py"), "w", encoding="utf-8"
        ) as fh_:
            fh_.write(body)

    class FileClient:
        def cache_dir(self, source, saltenv, **kwargs):
            return [os.path.join(cachedir, "files", saltenv, "_modules", "foo.py")]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    return FileClient()


def _synced(extension_modules):
    path = os.path.join(extension_modules, "modules", "foo.py")
    with salt.utils.files.fopen(path, encoding="utf-8") as fh_:
        return fh_.read().strip()


@pytest.mark.parametrize(
    "saltenv,expected",
    [
        (["qa"], "VERSION = '1.1'"),
        (["base"], "VERSION = '1.0'"),
    ],
)
def test_sync_single_saltenv(opts, extension_modules, fileclient, saltenv, expected):
    with patch("salt.fileclient.get_file_client", return_value=fileclient):
        salt.utils.extmods.sync(opts, "modules", saltenv=saltenv)
    assert _synced(extension_modules) == expected


def test_sync_multiple_saltenvs_warns_about_the_overwrite(
    opts, extension_modules, fileclient, caplog
):
    """
    All saltenvs share one flat ``extension_modules`` directory, so the last
    saltenv synced wins for any module name they have in common. That is
    long-standing behavior; make sure it is at least logged, since it is
    otherwise invisible and looks like the wrong saltenv was used.
    """
    with caplog.at_level(logging.WARNING, logger="salt.utils.extmods"):
        with patch("salt.fileclient.get_file_client", return_value=fileclient):
            salt.utils.extmods.sync(opts, "modules", saltenv=["qa", "base"])

    assert _synced(extension_modules) == "VERSION = '1.0'"
    assert "exists in more than one of the saltenvs being synced" in caplog.text


def test_sync_single_saltenv_does_not_warn(opts, fileclient, caplog):
    with caplog.at_level(logging.WARNING, logger="salt.utils.extmods"):
        with patch("salt.fileclient.get_file_client", return_value=fileclient):
            salt.utils.extmods.sync(opts, "modules", saltenv=["qa"])

    assert "exists in more than one of the saltenvs being synced" not in caplog.text
