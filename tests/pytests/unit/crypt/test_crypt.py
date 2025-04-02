"""
tests.pytests.unit.test_crypt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for salt's crypt module
"""

import uuid

import pytest

import salt.crypt
import salt.master
import salt.payload
import salt.utils.files
from tests.conftest import FIPS_TESTRUN
from tests.support.helpers import dedent

from . import PRIV_KEY, PRIV_KEY2, PUB_KEY, PUB_KEY2


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


@pytest.mark.skipif(FIPS_TESTRUN, reason="Legacy key can not be loaded in FIPS mode")
def test_verify_signature(tmp_path):
    tmp_path.joinpath("foo.pem").write_text(PRIV_KEY.strip())
    tmp_path.joinpath("foo.pub").write_text(PUB_KEY.strip())
    tmp_path.joinpath("bar.pem").write_text(PRIV_KEY2.strip())
    tmp_path.joinpath("bar.pub").write_text(PUB_KEY2.strip())
    msg = b"foo bar"
    sig = salt.crypt.sign_message(str(tmp_path.joinpath("foo.pem")), msg)
    assert salt.crypt.verify_signature(str(tmp_path.joinpath("foo.pub")), msg, sig)


@pytest.mark.skipif(FIPS_TESTRUN, reason="Legacy key can not be loaded in FIPS mode")
def test_verify_signature_bad_sig(tmp_path):
    tmp_path.joinpath("foo.pem").write_text(PRIV_KEY.strip())
    tmp_path.joinpath("foo.pub").write_text(PUB_KEY.strip())
    tmp_path.joinpath("bar.pem").write_text(PRIV_KEY2.strip())
    tmp_path.joinpath("bar.pub").write_text(PUB_KEY2.strip())
    msg = b"foo bar"
    sig = salt.crypt.sign_message(str(tmp_path.joinpath("foo.pem")), msg)
    assert not salt.crypt.verify_signature(str(tmp_path.joinpath("bar.pub")), msg, sig)


def test_read_or_generate_key_string(tmp_path):
    keyfile = tmp_path / ".aes"
    assert not keyfile.exists()
    first_key = salt.crypt.Crypticle.read_key(keyfile)
    assert first_key is None
    assert not keyfile.exists()
    salt.crypt.Crypticle.write_key(keyfile)
    second_key = salt.crypt.Crypticle.read_key(keyfile)
    assert second_key is not None


def test_dropfile_contents(tmp_path, master_opts):
    salt.crypt.dropfile(str(tmp_path), master_opts["user"], master_id=master_opts["id"])
    with salt.utils.files.fopen(str(tmp_path / ".dfn"), "r") as fp:
        assert master_opts["id"] == fp.read()


def test_master_keys_without_cluster_id(tmp_path, master_opts):
    master_opts["pki_dir"] = str(tmp_path)
    assert master_opts["cluster_id"] is None
    assert master_opts["cluster_pki_dir"] is None
    mkeys = salt.crypt.MasterKeys(master_opts)
    expected_master_pub = str(tmp_path / "master.pub")
    expected_master_rsa = str(tmp_path / "master.pem")
    assert expected_master_pub == mkeys.master_pub_path
    assert expected_master_rsa == mkeys.master_rsa_path
    assert mkeys.cluster_pub_path is None
    assert mkeys.cluster_rsa_path is None
    assert mkeys.pub_path == expected_master_pub
    assert mkeys.rsa_path == expected_master_rsa
    assert mkeys.key == mkeys.master_key


def test_master_keys_with_cluster_id(tmp_path, master_opts):
    master_pki_path = tmp_path / "master_pki"
    cluster_pki_path = tmp_path / "cluster_pki"
    # The paths need to exist
    master_pki_path.mkdir()
    cluster_pki_path.mkdir()
    (cluster_pki_path / "peers").mkdir()

    master_opts["pki_dir"] = str(master_pki_path)
    master_opts["cluster_id"] = "cluster1"
    master_opts["cluster_pki_dir"] = str(cluster_pki_path)

    mkeys = salt.crypt.MasterKeys(master_opts)

    expected_master_pub = str(master_pki_path / "master.pub")
    expected_master_rsa = str(master_pki_path / "master.pem")
    expected_cluster_pub = str(cluster_pki_path / "cluster.pub")
    expected_cluster_rsa = str(cluster_pki_path / "cluster.pem")
    assert expected_master_pub == mkeys.master_pub_path
    assert expected_master_rsa == mkeys.master_rsa_path
    assert expected_cluster_pub == mkeys.cluster_pub_path
    assert expected_cluster_rsa == mkeys.cluster_rsa_path
    assert mkeys.pub_path == expected_cluster_pub
    assert mkeys.rsa_path == expected_cluster_rsa
    assert mkeys.key == mkeys.cluster_key


def test_pwdata_decrypt():
    key_string = dedent(
        """
        -----BEGIN RSA PRIVATE KEY-----
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
    )

    pwdata = (
        b"V\x80+b\xca\x06M\xb6\x12\xc6\xe8\xf2\xb5\xbb\xd8m\xc0\x97\x9a\xeb\xb9q\x19\xc3"
        b'\xcdi\xb84\x90\xaf\x12kT\xe2@u\xd6\xe8T\x89\xa3\xc7\xb2Y\xd1N\x00\xa9\xc0"\xbe'
        b"\xed\xb1\xc3\xb7^\xbf\xbd\x8b\x13\xd3/L\x1b\xa1`\xe2\xea\x03\x98\x82\xf3uS&|"
        b'\xe5\xd8J\xce\xfc\x97\x8d\x0b\x949\xc0\xbd^\xef\xc6\xfd\xce\xbb\x1e\xd0"(m\xe1'
        b"\x95\xfb\xc8/\x07\x93\xb8\xda\x8f\x99\xfe\xdc\xd5\xcb\xdb\xb2\xf11M\xdbD\xcf"
        b"\x95\x13p\r\xa4\x1c{\xd5\xdb\xc7\xe5\xaf\x95F\x97\xa9\x00p~\xb5\xec\xa4.\xd0"
        b"\xa4\xb4\xf4f\xcds,Y/\xa1:WF\xb8\xc7\x07\xaa\x0b<'~\x1b$D9\xd4\x8d\xf0x\xc5"
        b"\xee\xa8:\xe6\x00\x10\xc5i\x11\xc7]C8\x05l\x8b\x9b\xc3\x83e\xf7y\xadi:0\xb4R"
        b"\x1a(\x04&yL8\x19s\n\x11\x81\xfd?\xfb2\x80Ll\xa1\xdc\xc9\xb6P\xca\x8d'\x11\xc1"
        b"\x07\xa5\xa1\x058\xc7\xce\xbeb\x92\xbf\x0bL\xec\xdf\xc3M\x83\xfb$\xec\xd5\xf9"
    )
    assert salt.crypt.pwdata_decrypt(key_string, pwdata) == "1234"
