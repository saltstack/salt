import hashlib
import hmac
import os

import pytest
from cryptography.hazmat.backends.openssl import backend
from cryptography.hazmat.primitives import serialization

import salt.crypt as crypt
import salt.utils.files
import salt.utils.stringutils
from tests.conftest import FIPS_TESTRUN
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


OPENSSL_ENCRYPTED_KEY = """
-----BEGIN RSA PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: AES-256-CBC,12E2FE8CA93672B629477073867DE7E4

3wgKQlgjT3G+8rIQt97AXMDByh5u9JMZPYOB9/wg3iC3qoJXfoFAsCNUjODJBnkI
j9Zgj/bOCaSM3UshMQXmYY+2Rfi1SVQPnETlqEH/plMZS38tB8mN5pBdthgGTw6c
rhpj/S23eZT5d+z5ODeVYlWCVhx8CtE8OQEzOQk8dxLWbVHhvgC3uJGWOPR3P7VM
BlxH5LxWRCrC8vzbnwwaJnX8BTQ7fc4qeGwHlXBjpnxQhxO27pEj08NQ0/lfKh1b
seX5uiCjuQhHFKNGTuA16rQIe6BkYRHIWCDhySftl/lqSfLQif0OAXaHEdL2EdIS
ySD12RYyNUDotEzYFF+qzJ5OAtraqvc8kYror7oN52bHKCjJyrp4+DWA4/N7FjTV
+FqUyJNKqw1DAQAxlZlq+GgNyi8+g/Zs2TKTc/ZXaPLjtWYOQEQkYaNBoaD3ydY3
c7x+uQtJLVW9BF9FSl9A7BItpqZQWKiHiGtUdhYOkemlR+zMatjBe/eTq8LrnEDa
IyI+rRo1PSDAz3n1pdEAzGAOeqwT+j7YG9O8+dybMY5FcAtiiPX21nIpmP+Rtx4X
GqzHsT7nM6QG4O8GPKuK6TniG+Q0doNWomwuau/cjQgL4C+yFiX3kIPpHz9kA/aS
NL1SJqSsvc3D/KlRbHXaJZJyhmzDuEbQynkaAdvejiajlJWAwA3BZWw1RUK7Wn8m
XcNPJL3g02uKq8SUDgVQl/cx4QawuWri2Xh8/xakNYWzNU2feoWBmV+gN2qDSxyz
Qi+xu3CzdJVrPs71lW0rEAIQvU3K3Umava9M4CUF6R7N9+Zv+m1EuMQs0IGt8VCY
Wo1KY5PAb/V718d1C3I6kXvLSDXG8xqyEleilPLhKCRGPK+2g0nGYu562EV1i6by
gr+PLnFJTfgHEzwIfsqfNoR8ReQ6AJKJoniQr4vqex9xtifuhes0odpqmUB4/B2C
UfY/SpJR6tzdrGndpB/vb1vjHumHklHHWrLONtz70BhR8Zaisc7SCmL5bFgWqzMC
MJKPulRRGQCPAzy5OI/ZULY8+dzlva1MyoCYlWjeUtcUAy+9dyA8GZv75ez9g71b
10nNINDcvGG7zWShSYrAKrvLlsoE7eZ+flG+XhI2CfiC9/zHBzy/slbaH9H+1tlO
VWKiw6iBb2TEvBk4Wpk2nUFlWKtkkBVAlgbShbE2K8pTHrJeIRv5J897k693NFZE
DjVVJirzMv/OiZTami0qBQ4nDtUZpH8FsFZ8DtREkhROsDmrjq9PGkOVaxEyF/ke
avJT34gp4OoNWj7/Rd1YNbGiWjMEB3zi9y1Q6Ufiod9ZlK3RQb4tNrpzDn/msdJo
pIkuByWjXjF4YQRKtAoeCn+CWiY7L/Qi8X7jmX27JLILlZPtTJ+aNp3eCr6ZX0dW
y0uhN89sgMewlvDA/pduL/VJRHUBZC2eD8FbD7p6K+yRKhdciS9A8F6aIhx615s6
mngRBfwzh8ST6yQgLwCgle/XaRYTWJKjzAe3lkaIBBhHpeuq1UMAjunoS8JnLNiy
xQJ0PznzY57sYKpIiClwMjfpnX47nTU2DFWuPEXvBtG1xMjacGPbVrUslesY5bii
-----END RSA PRIVATE KEY-----
"""


@pytest.fixture
def openssl_encrypted_key():
    return OPENSSL_ENCRYPTED_KEY


@pytest.fixture
def passphrase():
    return "pass1234"


@pytest.fixture
def signing_algorithm():
    if FIPS_TESTRUN:
        return salt.crypt.PKCS1v15_SHA224
    return salt.crypt.PKCS1v15_SHA1


@pytest.fixture
def encryption_algorithm():
    if FIPS_TESTRUN:
        return salt.crypt.OAEP_SHA224
    return salt.crypt.OAEP_SHA1


SIG_SHA224 = (
    b'\x18)\xc3E|\x15\xebF\x0f\xe6\xc0\x10\xca\xd9~\x1d\xf14t\xc7\x14}\xda6Fk"#'
    b'Hl\x06\x13\xa9\xe3QlL\\\xf4`r\x88\x85\xc6#s\xcb"6\x1c\xdd\x07t\xd4\x84g'
    b"n\x0f\xcc\x1c\xee\xe7\x84T\xb7\xd1\xc80~\xdd\xf7+\x972b6\xf1\xe1\x00P"
    b"E\xb8\x86\xb3i\xa6*\xd2\xac\xb5\xcbStg\xfb*E9+\xf7\xc5\xc6X\x1e\xb9vY\xb7"
    b"kT[a\xe8\xe1\xd8\xdf'u\x00k\x13\xff\xe2\xd1\x91M\xa7U\xc9\x90z\xf0"
    b"\x03\xb2\xf3\x1bR\xbd\xc8\xe4B\xadJ\x91\x1e\x98\xea\x17\xa8;\x01\xcb"
    b"1\x07\x7f\xa2\xf3\xe6\x83\xed\x03m\xad\t&\x95\xc2Q\xfcs\xcbV\xd4\xa4\xc9n"
    b"\x8a\xbe\xcc3?.N\x1f8d{B\x8cp\xf8\xc8\x17\x90\x0e\x0c\x1a\x8dF\xb8"
    b'\x18\xf7\x97\xf0\x04L\xe6\xfb\xc1\xb0}\xa9\xb6?\xc0\xbd\x8a<\xac"5\xee@x'
    b"\xea\x1d\xa3\xffB\xa5\xbdt`\xa5\xe8p\xa3/\x18+\xec5\xb3]\x92\xaa\xd7\x9c"
    b"\x0b\x03`~\x00\r%\xc8"
)


@pytest.fixture
def signature():
    if FIPS_TESTRUN:
        return SIG_SHA224
    return SIG


@pytest.fixture
def private_key(passphrase, tmp_path):
    keypath = tmp_path / "keys"
    keypath.mkdir()
    keyname = "test"
    keysize = 2048
    return crypt.gen_keys(str(keypath), keyname, keysize, passphrase=passphrase)


def test_fips_mode():
    assert backend._fips_enabled == FIPS_TESTRUN


@pytest.mark.skipif(FIPS_TESTRUN, reason="Legacy key can not be loaded in FIPS mode")
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
        if FIPS_TESTRUN:
            assert keybytes.startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----\n")
        else:
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


@pytest.mark.skipif(FIPS_TESTRUN, reason="Legacy key can not be loaded in FIPS mode")
def test_private_key_signing(private_key, passphrase):
    lpriv = LegacyPrivateKey(private_key.encode(), passphrase.encode())
    priv = crypt.PrivateKey(private_key, passphrase)
    data = b"meh"
    signature = priv.sign(data)
    lsignature = lpriv.sign(data)
    assert lsignature == signature


@pytest.mark.skipif(FIPS_TESTRUN, reason="Legacy key can not be loaded in FIPS mode")
def test_legacy_public_key_verify(private_key, passphrase):
    lpriv = crypt.PrivateKey(private_key, passphrase)
    data = b"meh"
    signature = lpriv.sign(data)
    pubkey = LegacyPublicKey(private_key.replace(".pem", ".pub"))
    assert pubkey.verify(data, signature)


@pytest.mark.skipif(FIPS_TESTRUN, reason="Legacy key can not be loaded in FIPS mode")
def test_public_key_verify(private_key, passphrase):
    lpriv = LegacyPrivateKey(private_key.encode(), passphrase.encode())
    data = b"meh"
    signature = lpriv.sign(data)
    pubkey = crypt.PublicKey(private_key.replace(".pem", ".pub"))
    assert pubkey.verify(data, signature)


@pytest.mark.skipif(FIPS_TESTRUN, reason="Legacy key can not be loaded in FIPS mode")
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


@pytest.mark.skipif(FIPS_TESTRUN, reason="Legacy key can not be loaded in FIPS mode")
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


def test_encrypt_decrypt(private_key, passphrase, encryption_algorithm):
    pubkey = crypt.PublicKey(private_key.replace(".pem", ".pub"))
    enc = pubkey.encrypt(b"meh", algorithm=encryption_algorithm)
    privkey = crypt.PrivateKey(private_key, passphrase)
    assert privkey.decrypt(enc, algorithm=encryption_algorithm) == b"meh"


def test_sign_message(signature, signing_algorithm):
    key = salt.crypt.serialization.load_pem_private_key(PRIVKEY_DATA.encode(), None)
    with patch("salt.crypt.get_rsa_key", return_value=key):
        assert (
            salt.crypt.sign_message(
                "/keydir/keyname.pem", MSG, algorithm=signing_algorithm
            )
            == signature
        )


def test_sign_message_with_passphrase(signature, signing_algorithm):
    key = salt.crypt.serialization.load_pem_private_key(PRIVKEY_DATA.encode(), None)
    with patch("salt.crypt.get_rsa_key", return_value=key):
        assert (
            salt.crypt.sign_message(
                "/keydir/keyname.pem",
                MSG,
                passphrase="password",
                algorithm=signing_algorithm,
            )
            == signature
        )


def test_verify_signature():
    with patch("salt.utils.files.fopen", mock_open(read_data=PUBKEY_DATA.encode())):
        assert salt.crypt.verify_signature("/keydir/keyname.pub", MSG, SIG)


def test_loading_encrypted_openssl_format(openssl_encrypted_key, passphrase, tmp_path):
    path = tmp_path / "key"
    path.write_text(openssl_encrypted_key)
    if FIPS_TESTRUN:
        with pytest.raises(ValueError):
            salt.crypt.get_rsa_key(path, passphrase)
    else:
        try:
            salt.crypt.get_rsa_key(path, passphrase)
        # BaseException to catch errors bubbling up from the cryptogrphy's
        # rust layer.
        except BaseException as exc:  # pylint: disable=broad-except
            pytest.fail(f"Unexpected exception: {exc}")


@pytest.mark.skipif(not FIPS_TESTRUN, reason="Only valid when in FIPS mode")
def test_fips_bad_signing_algo(private_key, passphrase):
    key = salt.crypt.PrivateKey(private_key, passphrase)
    with pytest.raises(salt.exceptions.UnsupportedAlgorithm):
        key.sign("meh", salt.crypt.PKCS1v15_SHA1)


@pytest.mark.skipif(not FIPS_TESTRUN, reason="Only valid when in FIPS mode")
def test_fips_bad_signing_algo_verification(private_key, passphrase):
    lpriv = LegacyPrivateKey(private_key.encode(), passphrase.encode())
    data = b"meh"
    signature = lpriv.sign(data)
    pubkey = salt.crypt.PublicKey(private_key.replace(".pem", ".pub"))
    # cryptogrpahy silently returns False on unsuppoted algorithm
    assert pubkey.verify(signature, salt.crypt.PKCS1v15_SHA1) is False


@pytest.mark.skipif(not FIPS_TESTRUN, reason="Only valid when in FIPS mode")
def test_fips_bad_encryption_algo(private_key, passphrase):
    key = salt.crypt.PublicKey(private_key.replace(".pem", ".pub"))
    with pytest.raises(salt.exceptions.UnsupportedAlgorithm):
        key.encrypt("meh", salt.crypt.OAEP_SHA1)


@pytest.mark.skipif(not FIPS_TESTRUN, reason="Only valid when in FIPS mode")
def test_fips_bad_decryption_algo(private_key, passphrase):
    pubkey = LegacyPublicKey(private_key.replace(".pem", ".pub"))
    data = pubkey.encrypt("meh")
    key = salt.crypt.PrivateKey(private_key, passphrase)
    with pytest.raises(salt.exceptions.UnsupportedAlgorithm):
        key.decrypt(data)
