"""
tests.pytests.unit.test_crypt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for salt's crypt module
"""

import os

import pytest

import salt.crypt
import salt.master
import salt.utils.files
import salt.utils.stringutils
from tests.pytests.unit.crypt import HAS_M2, HAS_PYCRYPTO_RSA
from tests.support.mock import MagicMock, MockCall, mock_open, patch

if HAS_PYCRYPTO_RSA:
    from tests.pytests.unit.crypt import RSA


def test_get_rsa_pub_key_bad_key(tmp_path):
    """
    get_rsa_pub_key raises InvalidKeyError when encountering a bad key
    """
    key_path = str(tmp_path / "key")
    with salt.utils.files.fopen(key_path, "w") as fp:
        fp.write("")
    with pytest.raises(salt.crypt.InvalidKeyError):
        salt.crypt.get_rsa_pub_key(key_path)


def test_verify_signature(pub_key, priv_key, tmp_path):
    tmp_path.joinpath("foo.pem").write_text(priv_key.strip())
    tmp_path.joinpath("foo.pub").write_text(pub_key.strip())
    msg = b"foo bar"
    sig = salt.crypt.sign_message(str(tmp_path.joinpath("foo.pem")), msg)
    assert salt.crypt.verify_signature(str(tmp_path.joinpath("foo.pub")), msg, sig)


def test_verify_signature_bad_sig(pub_key2, priv_key, tmp_path):
    tmp_path.joinpath("foo.pem").write_text(priv_key.strip())
    tmp_path.joinpath("bar.pub").write_text(pub_key2.strip())
    msg = b"foo bar"
    sig = salt.crypt.sign_message(str(tmp_path.joinpath("foo.pem")), msg)
    assert not salt.crypt.verify_signature(str(tmp_path.joinpath("bar.pub")), msg, sig)


@pytest.mark.skipif(not HAS_PYCRYPTO_RSA, reason="pycrypto >= 2.6 is not available")
@pytest.mark.skipif(HAS_M2, reason="m2crypto is used by salt.crypt if installed")
@pytest.mark.slow_test
def test_gen_keys():
    open_priv_wb = MockCall("/keydir{}keyname.pem".format(os.sep), "wb+")
    open_pub_wb = MockCall("/keydir{}keyname.pub".format(os.sep), "wb+")

    with patch.multiple(
        os,
        umask=MagicMock(),
        chmod=MagicMock(),
        access=MagicMock(return_value=True),
    ):
        with patch("salt.utils.files.fopen", mock_open()) as m_open, patch(
            "os.path.isfile", return_value=True
        ):
            result = salt.crypt.gen_keys("/keydir", "keyname", 2048)
            assert result == "/keydir{}keyname.pem".format(os.sep), result
            assert open_priv_wb not in m_open.calls
            assert open_pub_wb not in m_open.calls

        with patch("salt.utils.files.fopen", mock_open()) as m_open, patch(
            "os.path.isfile", return_value=False
        ):
            salt.crypt.gen_keys("/keydir", "keyname", 2048)
            assert open_priv_wb in m_open.calls
            assert open_pub_wb in m_open.calls


@pytest.mark.skipif(not HAS_PYCRYPTO_RSA, reason="pycrypto >= 2.6 is not available")
@pytest.mark.skipif(HAS_M2, reason="m2crypto is used by salt.crypt if installed")
@pytest.mark.slow_test
def test_gen_keys_with_passphrase():
    key_path = os.path.join(os.sep, "keydir")
    open_priv_wb = MockCall(os.path.join(key_path, "keyname.pem"), "wb+")
    open_pub_wb = MockCall(os.path.join(key_path, "keyname.pub"), "wb+")

    with patch.multiple(
        os,
        umask=MagicMock(),
        chmod=MagicMock(),
        chown=MagicMock(),
        access=MagicMock(return_value=True),
    ):
        with patch("salt.utils.files.fopen", mock_open()) as m_open, patch(
            "os.path.isfile", return_value=True
        ):
            assert salt.crypt.gen_keys(
                key_path, "keyname", 2048, passphrase="password"
            ) == os.path.join(key_path, "keyname.pem")
            result = salt.crypt.gen_keys(
                key_path, "keyname", 2048, passphrase="password"
            )
            assert result == os.path.join(key_path, "keyname.pem"), result
            assert open_priv_wb not in m_open.calls
            assert open_pub_wb not in m_open.calls

        with patch("salt.utils.files.fopen", mock_open()) as m_open, patch(
            "os.path.isfile", return_value=False
        ):
            salt.crypt.gen_keys(key_path, "keyname", 2048)
            assert open_priv_wb in m_open.calls
            assert open_pub_wb in m_open.calls


@pytest.mark.skipif(not HAS_PYCRYPTO_RSA, reason="pycrypto >= 2.6 is not available")
@pytest.mark.skipif(HAS_M2, reason="m2crypto is used by salt.crypt if installed")
def test_sign_message(priv_key, msg, sig):
    key = RSA.importKey(priv_key)
    with patch("salt.crypt.get_rsa_key", return_value=key):
        assert sig == salt.crypt.sign_message("/keydir/keyname.pem", msg)


@pytest.mark.skipif(not HAS_PYCRYPTO_RSA, reason="pycrypto >= 2.6 is not available")
@pytest.mark.skipif(HAS_M2, reason="m2crypto is used by salt.crypt if installed")
def test_sign_message_with_passphrase(priv_key, msg, sig):
    key = RSA.importKey(priv_key)
    with patch("salt.crypt.get_rsa_key", return_value=key):
        assert sig == salt.crypt.sign_message(
            "/keydir/keyname.pem", msg, passphrase="password"
        )


@pytest.mark.skipif(
    not HAS_M2 and not HAS_PYCRYPTO_RSA,
    reason="No crypto library found. Install either M2Crypto or Cryptodome to run this test",
)
def test_pwdata_decrypt():
    key_string = """-----BEGIN RSA PRIVATE KEY-----
MIIEpQIBAAKCAQEAzhBRyyHa7b63RLE71uKMKgrpulcAJjaIaN68ltXcCvy4w9pi
Kj+4I3Qp6RvUaHOEmymqyjOMjQc6iwpe0scCFqh3nUk5YYaLZ3WAW0htQVlnesgB
ZiBg9PBeTQY/LzqtudL6RCng/AX+fbnCsddlIysRxnUoNVMvz0gAmCY2mnTDjcTt
pyxuk2T0AHSHNCKCalm75L1bWDFF+UzFemf536tBfBUGRWR6jWTij85vvCntxHS/
HdknaTJ50E7XGVzwBJpCyV4Y2VXuW/3KrCNTqXw+jTmEw0vlcshfDg/vb3IxsUSK
5KuHalKq/nUIc+F4QCJOl+A10goGdIfYC1/67QIDAQABAoIBAAOP+qoFWtCTZH22
hq9PWVb8u0+yY1lFxhPyDdaZueUiu1r/coUCdv996Z+TEJgBr0AzdzVpsLtbbaKr
ujnwoNOdc/vvISPTfKN8P4zUcrcXgZd4z7VhR+vUH/0652q8m/ZDdHorMy2IOP8Z
cAk9DQ2PmA4TRm+tkX0G5KO8vWLsK921aRMWdsKJyQ0lYxl7M8JWupFsCJFr/U+8
dAVtwnUiS7RnhBABZ1cfNTHYhXVAh4d+a9y/gZ00a66OGqPxiXfhjjDUZ6fGvWKN
FlhKWEg6YqIx/H4aNXkLI5Rzzhdx/c2ukNm7+X2veRcAW7bcTwk8wxJxciEP5pBi
1el9VE0CgYEA/lbzdE2M4yRBvTfYYC6BqZcn+BqtrAUc2h3fEy+p7lwlet0af1id
gWpYpOJyLc0AUfR616/m2y3PwEH/nMKDSTuU7o/qKNtlHW0nQcnhDCjTUydS3+J/
JM3dhfgVqi03rjqNcgHA2eOEwcu/OBZtiaC0wqKbuRZRtfGffyoO3ssCgYEAz2iw
wqu/NkA+MdQIxz/a3Is7gGwoFu6h7O+XU2uN8Y2++jSBw9AzzWj31YCvyjuJPAE+
gxHm6yOnNoLVn423NtibHejhabzHNIK6UImH99bSTKabsxfF2BX6v982BimU1jwc
bYykzws37oN/poPb5FTpEiAUrsd2bAMn/1S43icCgYEAulHkY0z0aumCpyUkA8HO
BvjOtPiGRcAxFLBRXPLL3+vtIQachLHcIJRRf+jLkDXfiCo7W4pm6iWzTbqLkMEG
AD3/qowPFAM1Hct6uL01efzmYsIp+g0o60NMhvnolRQu+Bm4yM30AyqjdHzYBjSX
5fyuru8EeSCal1j8aOHcpuUCgYEAhGhDH6Pg59NPYSQJjpm3MMA59hwV473n5Yh2
xKyO6zwgRT6r8MPDrkhqnwQONT6Yt5PbwnT1Q/t4zhXsJnWkFwFk1U1MSeJYEa+7
HZsPECs2CfT6xPRSO0ac00y+AmUdPT8WruDwfbSdukh8f2MCR9vlBsswKPvxH7dM
G3aMplUCgYEAmMFgB/6Ox4OsQPPC6g4G+Ezytkc4iVkMEcjiVWzEsYATITjq3weO
/XDGBYJoBhYwWPi9oBufFc/2pNtWy1FKKXPuVyXQATdA0mfEPbtsHjMFQNZbeKnm
0na/SysSDCK3P+9ijlbjqLjMmPEmhJxGWTJ7khnTTkfre7/w9ZxJxi8=
-----END RSA PRIVATE KEY-----"""
    pwdata = b"""\
V\x80+b\xca\x06M\xb6\x12\xc6\xe8\xf2\xb5\xbb\xd8m\xc0\x97\x9a\xeb\xb9q\x19\xc3\
\xcdi\xb84\x90\xaf\x12kT\xe2@u\xd6\xe8T\x89\xa3\xc7\xb2Y\xd1N\x00\xa9\xc0"\xbe\
\xed\xb1\xc3\xb7^\xbf\xbd\x8b\x13\xd3/L\x1b\xa1`\xe2\xea\x03\x98\x82\xf3uS&|\
\xe5\xd8J\xce\xfc\x97\x8d\x0b\x949\xc0\xbd^\xef\xc6\xfd\xce\xbb\x1e\xd0"(m\xe1\
\x95\xfb\xc8/\x07\x93\xb8\xda\x8f\x99\xfe\xdc\xd5\xcb\xdb\xb2\xf11M\xdbD\xcf\
\x95\x13p\r\xa4\x1c{\xd5\xdb\xc7\xe5\xaf\x95F\x97\xa9\x00p~\xb5\xec\xa4.\xd0\
\xa4\xb4\xf4f\xcds,Y/\xa1:WF\xb8\xc7\x07\xaa\x0b<\'~\x1b$D9\xd4\x8d\xf0x\xc5\
\xee\xa8:\xe6\x00\x10\xc5i\x11\xc7]C8\x05l\x8b\x9b\xc3\x83e\xf7y\xadi:0\xb4R\
\x1a(\x04&yL8\x19s\n\x11\x81\xfd?\xfb2\x80Ll\xa1\xdc\xc9\xb6P\xca\x8d\'\x11\xc1\
\x07\xa5\xa1\x058\xc7\xce\xbeb\x92\xbf\x0bL\xec\xdf\xc3M\x83\xfb$\xec\xd5\xf9\
"""
    assert "1234" == salt.crypt.pwdata_decrypt(key_string, pwdata)


@pytest.mark.skipif(HAS_M2, reason="Skip when m2crypto is installed")
def test_crypto_bad_key(cryptodome_key_path):
    """
    Load public key with an invalid header and validate it without m2crypto
    """
    key = salt.crypt.get_rsa_pub_key(cryptodome_key_path)
    assert key.can_encrypt()
