"""
Tests for the nacl runner
"""

import pytest

import salt.config
import salt.utils.stringutils
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
