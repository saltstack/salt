import hashlib
import hmac
import os

import pytest
from cryptography.hazmat.primitives import serialization

import salt.crypt as crypt
import salt.utils.files
import salt.utils.stringutils
from tests.support.mock import mock_open, patch

from . import (
    HAS_M2,
    MSG,
    PRIVKEY_DATA,
    PUBKEY_DATA,
    SIG,
    LegacyPrivateKey,
    LegacyPublicKey,
    legacy_gen_keys,
)

if HAS_M2:
    from . import EVP, RSA
else:
    from . import AES, PKCS1_OAEP


@pytest.fixture
def passphrase():
    return "pass1234"


@pytest.fixture
def private_key(passphrase, tmp_path):
    keypath = tmp_path / "keys"
    keypath.mkdir()
    keyname = "test"
    keysize = 2048
    return crypt.gen_keys(str(keypath), keyname, keysize, passphrase=passphrase)


def test_gen_keys_legacy(tmp_path):
    keypath = tmp_path / "keys"
    keypath.mkdir()
    passphrase = "pass1234"
    keyname = "test"
    keysize = 2048
    ret = legacy_gen_keys(str(keypath), keyname, keysize, passphrase=passphrase)
    with salt.utils.files.fopen(ret, "rb") as fp:
        keybytes = fp.read()
        assert keybytes.startswith(b"-----BEGIN RSA PRIVATE KEY-----\n")
        priv = serialization.load_pem_private_key(keybytes, passphrase.encode())
    with salt.utils.files.fopen(ret.replace(".pem", ".pub"), "rb") as fp:
        keybytes = fp.read()
        assert keybytes.startswith(b"-----BEGIN PUBLIC KEY-----\n")


def test_gen_keys(tmp_path):
    keypath = tmp_path / "keys"
    keypath.mkdir()
    passphrase = "pass1234"
    keyname = "test"
    keysize = 2048
    ret = crypt.gen_keys(str(keypath), keyname, keysize, passphrase=passphrase)
    with salt.utils.files.fopen(ret, "rb") as fp:
        keybytes = fp.read()
        assert keybytes.startswith(b"-----BEGIN RSA PRIVATE KEY-----\n")
        priv = serialization.load_pem_private_key(keybytes, passphrase.encode())
    with salt.utils.files.fopen(ret.replace(".pem", ".pub"), "rb") as fp:
        keybytes = fp.read()
        assert keybytes.startswith(b"-----BEGIN PUBLIC KEY-----\n")


def test_legacy_private_key_loading(private_key, passphrase):
    priv = LegacyPrivateKey(private_key.encode(), passphrase.encode())
    assert priv.key


def test_private_key_loading(private_key, passphrase):
    priv = crypt.PrivateKey(private_key, passphrase)
    assert priv.key


def test_private_key_signing(private_key, passphrase):
    lpriv = LegacyPrivateKey(private_key.encode(), passphrase.encode())
    priv = crypt.PrivateKey(private_key, passphrase)
    data = b"meh"
    signature = priv.sign(data)
    lsignature = lpriv.sign(data)
    assert lsignature == signature


def test_legacy_public_key_verify(private_key, passphrase):
    lpriv = crypt.PrivateKey(private_key, passphrase)
    data = b"meh"
    signature = lpriv.sign(data)
    pubkey = LegacyPublicKey(private_key.replace(".pem", ".pub"))
    assert pubkey.verify(data, signature)


def test_public_key_verify(private_key, passphrase):
    lpriv = LegacyPrivateKey(private_key.encode(), passphrase.encode())
    data = b"meh"
    signature = lpriv.sign(data)
    pubkey = crypt.PublicKey(private_key.replace(".pem", ".pub"))
    assert pubkey.verify(data, signature)


def test_public_key_encrypt(private_key, passphrase):
    pubkey = crypt.PublicKey(private_key.replace(".pem", ".pub"))
    data = b"meh"
    enc = pubkey.encrypt(data)

    lpriv = LegacyPrivateKey(private_key.encode(), passphrase.encode())
    if HAS_M2:
        dec = lpriv.key.private_decrypt(enc, RSA.pkcs1_oaep_padding)
    else:
        cipher = PKCS1_OAEP.new(lpriv.key)
        dec = cipher.decrypt(enc)

    assert data == dec


def test_private_key_decrypt(private_key, passphrase):
    lpubkey = LegacyPublicKey(private_key.replace(".pem", ".pub"))
    data = b"meh"
    enc = lpubkey.encrypt(data)
    priv = crypt.PrivateKey(private_key, passphrase)
    dec = priv.key.decrypt(
        enc,
        crypt.padding.OAEP(
            mgf=crypt.padding.MGF1(algorithm=crypt.hashes.SHA1()),
            algorithm=crypt.hashes.SHA1(),
            label=None,
        ),
    )

    assert data == dec


def test_legacy_aes_encrypt():
    """
    Test that the legacy aes encryption can be decrypted by cryptography
    """
    orig_data = b"meh"
    crypticle = salt.crypt.Crypticle({}, salt.crypt.Crypticle.generate_key_string())
    aes_key, hmac_key = crypticle.keys
    pad = crypticle.AES_BLOCK_SIZE - len(orig_data) % crypticle.AES_BLOCK_SIZE
    data = orig_data + salt.utils.stringutils.to_bytes(pad * chr(pad))
    iv_bytes = os.urandom(crypticle.AES_BLOCK_SIZE)
    iv_bytes = data[: crypticle.AES_BLOCK_SIZE]
    if HAS_M2:
        cypher = EVP.Cipher(
            alg="aes_192_cbc", key=aes_key, iv=iv_bytes, op=1, padding=False
        )
        encr = cypher.update(data)
        encr += cypher.final()
    else:
        cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
        encr = cypher.encrypt(data)

    data = iv_bytes + encr
    sig = hmac.new(hmac_key, data, hashlib.sha256).digest()
    assert orig_data == crypticle.decrypt(data + sig)


def test_aes_encrypt():
    """
    Test that cryptography aes encryption can be decrypted by the legacy libraries
    """
    orig_data = b"meh"
    crypticle = salt.crypt.Crypticle({}, salt.crypt.Crypticle.generate_key_string())

    data = crypticle.encrypt(orig_data)
    aes_key, hmac_key = crypticle.keys
    sig = data[-crypticle.SIG_SIZE :]
    data = data[: -crypticle.SIG_SIZE]
    if not isinstance(data, bytes):
        data = salt.utils.stringutils.to_bytes(data)
    mac_bytes = hmac.new(hmac_key, data, hashlib.sha256).digest()
    result = 0
    for zipped_x, zipped_y in zip(mac_bytes, sig):
        result |= zipped_x ^ zipped_y
    iv_bytes = data[: crypticle.AES_BLOCK_SIZE]
    data = data[crypticle.AES_BLOCK_SIZE :]
    if HAS_M2:
        cypher = EVP.Cipher(
            alg="aes_192_cbc", key=aes_key, iv=iv_bytes, op=0, padding=False
        )
        encr = cypher.update(data)
        data = encr + cypher.final()
    else:
        cypher = AES.new(aes_key, AES.MODE_CBC, iv_bytes)
        data = cypher.decrypt(data)
    data = data[: -data[-1]]
    assert orig_data == data


def test_sign_message():
    key = salt.crypt.serialization.load_pem_private_key(PRIVKEY_DATA.encode(), None)
    with patch("salt.crypt.get_rsa_key", return_value=key):
        assert SIG == salt.crypt.sign_message("/keydir/keyname.pem", MSG)


def test_sign_message_with_passphrase():
    key = salt.crypt.serialization.load_pem_private_key(PRIVKEY_DATA.encode(), None)
    with patch("salt.crypt.get_rsa_key", return_value=key):
        assert SIG == salt.crypt.sign_message(
            "/keydir/keyname.pem", MSG, passphrase="password"
        )


def test_verify_signature():
    with patch("salt.utils.files.fopen", mock_open(read_data=PUBKEY_DATA.encode())):
        assert salt.crypt.verify_signature("/keydir/keyname.pub", MSG, SIG)
