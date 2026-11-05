"""Exercise the runner and execution-module file APIs against real secretbox data."""

import pytest

import salt.modules.nacl
import salt.runners.nacl
import salt.utils.nacl

pytest.importorskip("nacl.secret")


@pytest.fixture
def configure_loader_modules(tmp_path):
    opts = {"pki_dir": str(tmp_path)}
    return {
        salt.modules.nacl: {"__opts__": opts},
        salt.runners.nacl: {"__opts__": opts},
        salt.utils.nacl: {"__salt__": {}},
    }


@pytest.mark.parametrize("api", [salt.modules.nacl, salt.runners.nacl])
def test_file_round_trip(api, tmp_path):
    keys = api.keygen()
    source = tmp_path / "plain.txt"
    encrypted = tmp_path / "encrypted.txt"
    decrypted = tmp_path / "decrypted.txt"
    source.write_bytes(b"a secret\nwith a second line")
    kwargs = {"sk": keys["sk"], "box_type": "secretbox"}

    assert (
        api.enc_file(str(source), out=str(encrypted), **kwargs) == f"Wrote: {encrypted}"
    )
    assert encrypted.read_bytes() != source.read_bytes()
    assert api.dec_file(str(encrypted), **kwargs) == source.read_bytes()
    assert (
        api.dec_file(str(encrypted), out=str(decrypted), **kwargs)
        == f"Wrote: {decrypted}"
    )
    assert decrypted.read_bytes() == source.read_bytes()
