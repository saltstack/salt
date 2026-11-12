"""Functional tests for the Salt key management API."""

import pytest

import salt.crypt
import salt.key
import salt.utils.crypt


@pytest.mark.windows_whitelisted
@pytest.mark.parametrize("keyname", [None, "generated-minion"])
def test_gen_keys_returns_public_key_fingerprint(master_opts, tmp_path, keyname):
    opts = master_opts.copy()
    opts["keysize"] = 2048
    keydir = tmp_path / "generated-keys"
    opts["pki_dir"] = str(keydir)
    # Exercise the default name independently of the CLI's gen_keys option.
    opts.pop("gen_keys", None)
    key = salt.key.Key(opts)
    name = keyname or "minion"

    fingerprint = key.gen_keys(keyname=keyname, keysize=2048)

    private_path = keydir / f"{name}.pem"
    public_path = keydir / f"{name}.pub"
    private_pem = private_path.read_bytes()
    public_pem = public_path.read_text(encoding="utf-8")
    assert salt.crypt.PrivateKey.from_bytes(private_pem).public_key().key_size == 2048
    assert fingerprint == salt.utils.crypt.pem_finger(key=public_pem)

    # Loading an existing keypair must return the same fingerprint without
    # replacing either key.
    assert key.gen_keys(keyname=keyname, keysize=2048) == fingerprint
    assert private_path.read_bytes() == private_pem
    assert public_path.read_text(encoding="utf-8") == public_pem
