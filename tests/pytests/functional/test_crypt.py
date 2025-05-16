import pathlib

import pytest

import salt.crypt


@pytest.mark.windows_whitelisted
def test_generated_keys(master_opts, tmp_path):
    master_opts["pki_dir"] = str(tmp_path)
    master_keys = salt.crypt.MasterKeys(master_opts)
    master_keys.find_or_create_keys(name="aaa", keysize=2048)
    priv = pathlib.Path(master_keys.opts["pki_dir"]) / "aaa.pem"
    pub = priv.with_suffix(".pub")
    assert "\r" not in priv.read_text(encoding="utf-8")
    assert "\r" not in pub.read_text(encoding="utf-8")
