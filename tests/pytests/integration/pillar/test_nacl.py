"""Load the NaCl external pillar with the retained renderer and execution module."""

import base64

import pytest

import salt.config
import salt.loader
import salt.utils.yaml
from tests.conftest import FIPS_TESTRUN

nacl_public = pytest.importorskip("nacl.public")

pytestmark = pytest.mark.skipif(FIPS_TESTRUN, reason="NaCl is unavailable in FIPS mode")


def test_ext_pillar_decrypts_nested_data(tmp_path):
    key = nacl_public.PrivateKey.generate()
    sk_file = tmp_path / "nacl_sk"
    sk_file.write_bytes(base64.b64encode(bytes(key)))
    sk_file.chmod(0o600)
    config_dir = tmp_path / "master.d"
    config_dir.mkdir()
    (config_dir / "nacl.conf").write_text(
        salt.utils.yaml.safe_dump({"nacl.config": {"sk_file": str(sk_file)}}),
        encoding="utf-8",
    )
    master_config = tmp_path / "master"
    master_config.write_text("", encoding="utf-8")
    opts = salt.config.master_config(str(master_config))
    ciphertext = base64.b64encode(
        nacl_public.SealedBox(key.public_key).encrypt(b"test")
    ).decode()
    functions = salt.loader.minion_mods(opts)
    pillars = salt.loader.pillars(opts, functions)
    data = {"nested": [f"NACL[{ciphertext}]", "unchanged"], "number": 42}

    assert pillars["nacl"]("test-minion", data) == {
        "nested": [b"test", "unchanged"],
        "number": 42,
    }
