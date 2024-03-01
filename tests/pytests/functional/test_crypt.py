import pathlib

import pytest

import salt.crypt


@pytest.mark.windows_whitelisted
def test_generated_keys(tmp_path):
    priv = salt.crypt.gen_keys(tmp_path, "aaa", 2048)
    assert "\r" not in pathlib.Path(priv).read_text()
    assert "\r" not in pathlib.Path(priv.replace(".pem", ".pub")).read_text()
