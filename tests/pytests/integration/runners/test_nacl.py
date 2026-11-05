"""
Tests for the nacl runner
"""

import ast
from pathlib import Path

import pytest

import salt.config
import salt.utils.stringutils
import salt.utils.yaml
from tests.conftest import FIPS_TESTRUN
from tests.support.mock import patch

pytest.importorskip("nacl.public")
pytest.importorskip("nacl.secret")

import salt.runners.nacl as nacl

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def minion_opts():
    return salt.config.minion_config(None)


@pytest.fixture
def test_data():
    unencrypted_data = salt.utils.stringutils.to_bytes("hello")
    return unencrypted_data


def test_keygen(minion_opts):
    """
    Test keygen
    """
    # Store the data
    with patch("salt.runners.nacl.__opts__", minion_opts, create=True):
        ret = nacl.keygen()
    assert "pk" in ret
    assert "sk" in ret


def test_enc(test_data, minion_opts):
    """
    Test keygen
    """
    # Store the data
    with patch("salt.runners.nacl.__opts__", minion_opts, create=True):
        ret = nacl.keygen()
        assert "pk" in ret
        assert "sk" in ret
        pk = ret["pk"]
        sk = ret["sk"]

        # Encrypt with pk
        ret = nacl.enc(
            data=test_data,
            pk=pk,
        )


def test_enc_dec(test_data, minion_opts):
    """
    Store, list, fetch, then flush data
    """
    # Store the data
    with patch("salt.runners.nacl.__opts__", minion_opts, create=True):
        ret = nacl.keygen()
        assert "pk" in ret
        assert "sk" in ret
        pk = ret["pk"]
        sk = ret["sk"]

        # Encrypt with pk
        encrypted_data = nacl.enc(
            data=test_data,
            pk=pk,
        )

        # Decrypt with sk
        ret = nacl.dec(
            data=encrypted_data,
            sk=sk,
        )
        assert test_data == ret


def test_sealedbox_enc_dec(test_data, minion_opts):
    """
    Generate keys, encrypt, then decrypt.
    """
    # Store the data
    with patch("salt.runners.nacl.__opts__", minion_opts, create=True):
        ret = nacl.keygen()
        assert "pk" in ret
        assert "sk" in ret
        pk = ret["pk"]
        sk = ret["sk"]

        # Encrypt with pk
        encrypted_data = nacl.sealedbox_encrypt(
            data=test_data,
            pk=pk,
        )

        # Decrypt with sk
        ret = nacl.sealedbox_decrypt(
            data=encrypted_data,
            sk=sk,
        )
        assert test_data == ret


def test_secretbox_enc_dec(test_data, minion_opts):
    """
    Generate keys, encrypt, then decrypt.
    """
    # Store the data
    with patch("salt.runners.nacl.__opts__", minion_opts, create=True):
        ret = nacl.keygen()
        assert "pk" in ret
        assert "sk" in ret
        pk = ret["pk"]
        sk = ret["sk"]

        # Encrypt with pk
        encrypted_data = nacl.secretbox_encrypt(
            data=test_data,
            sk=sk,
        )

        # Decrypt with sk
        ret = nacl.secretbox_decrypt(
            data=encrypted_data,
            sk=sk,
        )
        assert test_data == ret


def test_enc_dec_no_pk_no_sk(test_data, minion_opts):
    """
    Store, list, fetch, then flush data
    """
    # Store the data
    with patch("salt.runners.nacl.__opts__", minion_opts, create=True):
        ret = nacl.keygen()
        assert "pk" in ret
        assert "sk" in ret
        pk = ret["pk"]
        sk = ret["sk"]

        # Encrypt with pk
        with pytest.raises(Exception, match="no pubkey or pk_file found"):
            ret = nacl.enc(
                data=test_data,
                pk=None,
            )

        encrypted_data = test_data  # dummy data, should get exception
        # Decrypt with sk
        with pytest.raises(Exception, match="no key or sk_file found"):
            ret = nacl.dec(
                data=encrypted_data,
                sk=None,
            )


@pytest.mark.skipif(FIPS_TESTRUN, reason="NaCl is unavailable in FIPS mode")
def test_cli_enc_dec_with_master_d_config(salt_factories, tmp_path, minion_opts):
    """Load the built-in runner and read key paths only from master.d."""
    master = salt_factories.salt_master_daemon("nacl-config-master")
    with patch("salt.runners.nacl.__opts__", minion_opts, create=True):
        keys = nacl.keygen()
    sk_file = tmp_path / "nacl_sk"
    pk_file = tmp_path / "nacl_pk"
    sk_file.write_bytes(keys["sk"])
    sk_file.chmod(0o600)
    pk_file.write_bytes(keys["pk"])
    config = {"nacl.config": {"sk_file": str(sk_file), "pk_file": str(pk_file)}}
    config_dir = Path(master.config["conf_file"]).parent / "master.d"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "nacl.conf").write_text(
        salt.utils.yaml.safe_dump(config), encoding="utf-8"
    )
    # No master daemon is needed, but the runner writes a job record here.
    (Path(master.config["cachedir"]) / "proc").mkdir(parents=True, exist_ok=True)
    cli = master.salt_run_cli()
    encrypted = cli.run("nacl.enc", data="test")
    assert encrypted.returncode == 0, encrypted
    # salt-run represents the runner's bytes return value with repr().
    ciphertext = ast.literal_eval(encrypted.stdout.strip()).decode()
    decrypted = cli.run("nacl.dec", data=ciphertext)
    assert decrypted.returncode == 0, decrypted
    assert ast.literal_eval(decrypted.stdout.strip()) == b"test", decrypted
