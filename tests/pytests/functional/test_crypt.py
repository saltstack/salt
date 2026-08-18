import pathlib

import pytest

import salt.crypt


@pytest.mark.windows_whitelisted
def test_generated_keys(tmp_path):
    priv = pathlib.Path(salt.crypt.gen_keys(tmp_path, "aaa", 2048))
    pub = priv.with_suffix(".pub")
    assert "\r" not in priv.read_text(encoding="utf-8")
    assert "\r" not in pub.read_text(encoding="utf-8")
