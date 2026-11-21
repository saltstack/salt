"""
Unit tests for salt.modules.ssh.check_key_file option handling.
"""

import pytest

import salt.modules.ssh as ssh
import salt.utils.files
from tests.support.mock import MagicMock, patch

# Real ed25519 key body. base64.b64decode(..., validate=True) accepts it.
_PUBKEY = "AAAAC3NzaC1lZDI1NTE5AAAAINEIiNXlqUlqiVg69lJkzMfyBWAansuwqW6bw7zox7kR"


@pytest.fixture
def configure_loader_modules():
    return {ssh: {"__salt__": {}, "__context__": {}}}


def _write_pubkey(path, options=None):
    prefix = ""
    if options:
        prefix = ",".join(options) + " "
    line = f"{prefix}ssh-ed25519 {_PUBKEY} root@domain\n"
    with salt.utils.files.fopen(path, "w") as key_fh:
        key_fh.write(line)


def _check_key_file(home, source, **kwargs):
    with patch.dict(
        ssh.__salt__,
        {
            "cp.cache_file": MagicMock(return_value=str(source)),
            "user.info": MagicMock(return_value={"home": str(home)}),
        },
    ):
        return ssh.check_key_file("user", "salt://key.pub", **kwargs)


def _key_paths(tmp_path):
    home = tmp_path / "home"
    source = tmp_path / "key.pub"
    auth = home / ".ssh" / "authorized_keys"
    auth.parent.mkdir(parents=True)
    return home, source, auth


def test_check_key_file_options_differ_reports_update(tmp_path):
    """
    State options that differ from the key on disk are an update.
    """
    home, source, auth = _key_paths(tmp_path)
    _write_pubkey(source)
    _write_pubkey(auth)

    ret = _check_key_file(home, source, options=["no-pty"])

    assert ret[_PUBKEY] == "update"


def test_check_key_file_options_equal_reports_exists(tmp_path):
    """
    State options that match the key on disk are not a change, even when
    the source file does not itself contain those options.
    """
    home, source, auth = _key_paths(tmp_path)
    _write_pubkey(source)
    _write_pubkey(auth, options=["no-pty"])

    ret = _check_key_file(home, source, options=["no-pty"])

    assert ret[_PUBKEY] == "exists"


def test_check_key_file_options_omitted_uses_source_file(tmp_path):
    """
    Omitting options keeps the previous comparison against the source file.
    """
    home, source, auth = _key_paths(tmp_path)
    _write_pubkey(source)
    _write_pubkey(auth)

    ret = _check_key_file(home, source)

    assert ret[_PUBKEY] == "exists"

    _write_pubkey(source, options=["no-pty"])
    ret = _check_key_file(home, source)

    assert ret[_PUBKEY] == "update"
