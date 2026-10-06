"""
    Unit tests for the salt.modules.nacl module
"""

import os

import pytest

import salt.utils.stringutils
from tests.support.mock import patch

pytest.importorskip("nacl.public")
pytest.importorskip("nacl.secret")

import salt.modules.nacl as nacl


@pytest.fixture
def configure_loader_modules(minion_opts):
    utils = salt.loader.utils(minion_opts)
    funcs = salt.loader.minion_mods(minion_opts, utils=utils)
    return {
        nacl: {
            "__opts__": minion_opts,
            "__utils__": utils,
            "__salt__": funcs,
        },
    }


@pytest.fixture
def test_keys():
    # Generate the keys
    ret = nacl.keygen()
    assert "pk" in ret
    assert "sk" in ret
    return ret["pk"], ret["sk"]


@pytest.fixture
def test_data():
    unencrypted_data = salt.utils.stringutils.to_bytes("hello")
    return unencrypted_data


def test_fips_mode():
    """
    Nacl module does not load when fips_mode is True
    """
    opts = {"fips_mode": True}
    with patch("salt.modules.nacl.__opts__", opts, create=True):
        ret = salt.modules.nacl.__virtual__()
        assert ret == (False, "nacl module not available in FIPS mode")


def test_keygen(test_keys):
    """
    Test keygen
    """
    test_pk, test_sk = test_keys
    assert len(test_pk) == 44
    assert len(test_sk) == 44


def test_enc_dec(test_data, test_keys):
    """
    Generate keys, encrypt, then decrypt.

    Use secretbox here: the default sealedbox path calls libsodium's sealed-box
    helpers, which have intermittently segfaulted in CI when the onedir Python
    loads PyNaCl from a separate site-packages tree (mixed ABI).
    """
    _pk, test_sk = test_keys
    encrypted_data = nacl.enc(data=test_data, sk=test_sk, box_type="secretbox")
    decrypted_data = nacl.dec(data=encrypted_data, sk=test_sk, box_type="secretbox")
    assert test_data == decrypted_data


@pytest.mark.skipif(
    os.environ.get("ONEDIR_TESTRUN", "0") == "1",
    reason="Sealed-box PyNaCl path can segfault under onedir test runs (mixed native ABI).",
)
def test_sealedbox_enc_dec(test_data, test_keys):
    """
    Generate keys, encrypt, then decrypt.
    """
    # Encrypt with pk
    test_pk, test_sk = test_keys
    encrypted_data = nacl.sealedbox_encrypt(data=test_data, pk=test_pk)

    # Decrypt with sk
    decrypted_data = nacl.sealedbox_decrypt(data=encrypted_data, sk=test_sk)

    assert test_data == decrypted_data


def test_secretbox_enc_dec(test_data, test_keys):
    """
    Generate keys, encrypt, then decrypt.
    """
    # Encrypt with sk
    test_pk, test_sk = test_keys
    encrypted_data = nacl.secretbox_encrypt(data=test_data, sk=test_sk)

    # Decrypt with sk
    decrypted_data = nacl.secretbox_decrypt(data=encrypted_data, sk=test_sk)

    assert test_data == decrypted_data
