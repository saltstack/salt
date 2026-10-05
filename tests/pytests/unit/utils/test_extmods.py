"""
Tests for salt.utils.extmods
"""

import pytest

import salt.utils.extmods
from tests.support.mock import MagicMock, patch


@pytest.fixture
def opts(tmp_path):
    return {
        "extension_modules": str(tmp_path / "extmods"),
        "cachedir": str(tmp_path / "cache"),
        "extmod_whitelist": {},
        "extmod_blacklist": {},
        "clean_dynamic_modules": False,
    }


@pytest.fixture
def get_file_client():
    client = MagicMock()
    client.cache_dir.return_value = []
    with patch("salt.fileclient.get_file_client") as get_client:
        get_client.return_value.__enter__.return_value = client
        yield get_client


@pytest.mark.parametrize("force_local", [True, False])
def test_sync_passes_force_local_to_file_client(opts, get_file_client, force_local):
    """
    ``force_local`` lets a caller sync from the local file roots even when the
    minion is configured to use a remote file client.
    """
    salt.utils.extmods.sync(opts, "grains", force_local=force_local)
    get_file_client.assert_called_once_with(opts, pillar=False, force_local=force_local)


def test_sync_force_local_defaults_to_false(opts, get_file_client):
    salt.utils.extmods.sync(opts, "grains")
    get_file_client.assert_called_once_with(opts, pillar=False, force_local=False)


def test_sync_force_local_copies_grains_from_file_roots(minion_opts, tmp_path):
    """
    End to end: with a remote ``file_client`` configured, ``force_local=True``
    copies ``_grains`` from the local ``file_roots`` into the extension modules
    directory.
    """
    grains_dir = tmp_path / "srv" / "_grains"
    grains_dir.mkdir(parents=True)
    (grains_dir / "custom_grain.py").write_text("def main():\n    return {}\n")
    minion_opts.update(
        {
            "file_client": "remote",
            "file_roots": {"base": [str(tmp_path / "srv")]},
            "fileserver_backend": ["roots"],
            "cachedir": str(tmp_path / "cache"),
            "extension_modules": str(tmp_path / "extmods"),
            "clean_dynamic_modules": False,
        }
    )

    ret, touched = salt.utils.extmods.sync(
        minion_opts, "grains", saltenv=["base"], force_local=True
    )

    assert ret == ["grains.custom_grain"]
    assert touched is True
    assert (tmp_path / "extmods" / "grains" / "custom_grain.py").is_file()
