"""
tests.pytests.unit.test_crypt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for salt's crypt module
"""

import uuid

import pytest
import salt.crypt
import salt.master
import salt.utils.files


def test_get_rsa_pub_key_bad_key(tmp_path):
    """
    get_rsa_pub_key raises InvalidKeyError when encoutering a bad key
    """
    key_path = str(tmp_path / "key")
    with salt.utils.files.fopen(key_path, "w") as fp:
        fp.write("")
    with pytest.raises(salt.crypt.InvalidKeyError):
        salt.crypt.get_rsa_pub_key(key_path)


def test_cryptical_dumps_no_nonce():
    master_crypt = salt.crypt.Crypticle({}, salt.crypt.Crypticle.generate_key_string())
    data = {"foo": "bar"}
    ret = master_crypt.dumps(data)

    # Validate message structure
    assert isinstance(ret, bytes)
    une = master_crypt.decrypt(ret)
    une.startswith(master_crypt.PICKLE_PAD)
    assert salt.payload.loads(une[len(master_crypt.PICKLE_PAD) :]) == data

    # Validate load back to orig data
    assert master_crypt.loads(ret) == data


def test_cryptical_dumps_valid_nonce():
    nonce = uuid.uuid4().hex
    master_crypt = salt.crypt.Crypticle({}, salt.crypt.Crypticle.generate_key_string())
    data = {"foo": "bar"}
    ret = master_crypt.dumps(data, nonce=nonce)

    assert isinstance(ret, bytes)
    une = master_crypt.decrypt(ret)
    une.startswith(master_crypt.PICKLE_PAD)
    nonce_and_data = une[len(master_crypt.PICKLE_PAD) :]
    assert nonce_and_data.startswith(nonce.encode())
    assert salt.payload.loads(nonce_and_data[len(nonce) :]) == data

    assert master_crypt.loads(ret, nonce=nonce) == data


def test_cryptical_dumps_invalid_nonce():
    nonce = uuid.uuid4().hex
    master_crypt = salt.crypt.Crypticle({}, salt.crypt.Crypticle.generate_key_string())
    data = {"foo": "bar"}
    ret = master_crypt.dumps(data, nonce=nonce)
    assert isinstance(ret, bytes)
    with pytest.raises(salt.crypt.SaltClientError, match="Nonce verification error"):
        assert master_crypt.loads(ret, nonce="abcde")
