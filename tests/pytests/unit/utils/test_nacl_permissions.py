"""Private-key file permissions and keypair persistence."""

import pathlib

import pytest

import salt.utils.nacl as nacl
from tests.support.mock import MagicMock, patch

pytest.importorskip("nacl.public")


@pytest.mark.parametrize("windows", [False, True])
def test_keygen_explicit_files_and_permissions(tmp_path, windows):
    sk_file = str(tmp_path / "secret")
    pk_file = str(tmp_path / "public")
    owner = MagicMock()
    permissions = MagicMock()
    with patch("salt.utils.platform.is_windows", return_value=windows), patch(
        "salt.utils.win_functions.get_current_user",
        return_value="test-user",
        create=True,
    ), patch("salt.utils.win_dacl.set_owner", owner, create=True), patch(
        "salt.utils.win_dacl.set_permissions", permissions, create=True
    ):
        assert (
            nacl.keygen(sk_file, pk_file)
            == f"saved sk_file:{sk_file}  pk_file: {pk_file}"
        )
    secret = pathlib.Path(sk_file).read_bytes()
    public = pathlib.Path(pk_file).read_bytes()
    # Deriving the public key from the saved secret must reproduce the keypair.
    pathlib.Path(pk_file).unlink()
    assert nacl.keygen(sk_file, pk_file) == f"saved pk_file: {pk_file}"
    assert pathlib.Path(pk_file).read_bytes() == public
    assert len(secret) == 44
    if windows:
        owner.assert_called_once_with(sk_file, "test-user")
        permissions.assert_called_once_with(
            sk_file,
            "test-user",
            "full_control",
            "grant",
            reset_perms=True,
            protected=True,
        )
    else:
        assert pathlib.Path(sk_file).stat().st_mode & 0o7777 == 0o600
        owner.assert_not_called()
        permissions.assert_not_called()
    with pytest.raises(Exception, match="already exist"):
        nacl.keygen(sk_file, pk_file)
    assert pathlib.Path(sk_file).read_bytes() == secret
    assert pathlib.Path(pk_file).read_bytes() == public
