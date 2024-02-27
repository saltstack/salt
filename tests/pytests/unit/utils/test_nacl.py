"""
    Unit tests for the salt.utils.nacl module
"""

import os

import pytest

import salt.modules.config as config
import salt.utils.files
from tests.support.mock import patch

pytest.importorskip("nacl.public")
pytest.importorskip("nacl.secret")

import salt.utils.nacl as nacl


@pytest.fixture
def configure_loader_modules():
    return {
        nacl: {"__salt__": {"config.get": config.get}},
        config: {"__opts__": {}},
    }


@pytest.fixture(scope="module")
def test_keygen():
    """
    test nacl.keygen function

    Note: nacl.keygen returns base64 encoded values
    """
    ret = nacl.keygen()
    assert "sk" in ret
    assert "pk" in ret
    return ret


def test_fips_mode():
    """
    Nacl pillar doesn't load when fips_mode is True
    """
    opts = {"fips_mode": True}
    with patch("salt.utils.nacl.__opts__", opts, create=True):
        ret = salt.utils.nacl.__virtual__()
        assert ret == (False, "nacl utils not available in FIPS mode")


def test_keygen_sk_file(test_keygen):
    """
    test nacl.keygen function
    with sk_file set
    """
    with pytest.helpers.temp_file("test_keygen_sk_file") as fpath:
        with salt.utils.files.fopen(fpath, "wb") as wfh:
            wfh.write(test_keygen["sk"])

        # test sk_file
        ret = nacl.keygen(sk_file=fpath)
        assert f"saved pk_file: {fpath}.pub" == ret
        salt.utils.files.remove(str(fpath) + ".pub")


def test_keygen_keyfile(test_keygen):
    """
    test nacl.keygen function
    with keyfile set
    """
    with pytest.helpers.temp_file("test_keygen_keyfile") as fpath:
        with salt.utils.files.fopen(fpath, "wb") as wfh:
            wfh.write(test_keygen["sk"])

        ret = nacl.keygen(keyfile=fpath)
        assert f"saved pk_file: {fpath}.pub" == ret
        salt.utils.files.remove(str(fpath) + ".pub")


def test_enc_keyfile(test_keygen):
    """
    test nacl.enc function
    with keyfile and pk_file set
    """
    with pytest.helpers.temp_file("test_enc_keyfile") as fpath:
        with salt.utils.files.fopen(fpath, "wb") as wfh:
            wfh.write(test_keygen["sk"])
        with salt.utils.files.fopen(str(fpath) + ".pub", "wb") as wfhpub:
            wfhpub.write(test_keygen["pk"])

        kwargs = {
            "opts": {"pki_dir": os.path.dirname(fpath)},
            "keyfile": str(fpath),
            "pk_file": str(fpath) + ".pub",
        }
        ret = nacl.enc("blah", **kwargs)
        assert isinstance(ret, bytes)
        salt.utils.files.remove(str(fpath) + ".pub")


def test_enc_sk_file(test_keygen):
    """
    test nacl.enc function
    with sk_file and pk_file set
    """
    with pytest.helpers.temp_file("test_enc_sk_file") as fpath:
        with salt.utils.files.fopen(fpath, "wb") as wfh:
            wfh.write(test_keygen["sk"])
        with salt.utils.files.fopen(str(fpath) + ".pub", "wb") as wfhpub:
            wfhpub.write(test_keygen["pk"])

        kwargs = {
            "opts": {"pki_dir": os.path.dirname(fpath)},
            "sk_file": str(fpath),
            "pk_file": str(fpath) + ".pub",
        }
        ret = nacl.enc("blah", **kwargs)
        assert isinstance(ret, bytes)
        salt.utils.files.remove(str(fpath) + ".pub")


def test_dec_keyfile(test_keygen):
    """
    test nacl.dec function
    with keyfile and pk_file set
    """
    with pytest.helpers.temp_file("test_dec_keyfile") as fpath:
        with salt.utils.files.fopen(fpath, "wb") as wfh:
            wfh.write(test_keygen["sk"])
        with salt.utils.files.fopen(str(fpath) + ".pub", "wb") as wfhpub:
            wfhpub.write(test_keygen["pk"])

        kwargs = {
            "opts": {"pki_dir": os.path.dirname(fpath)},
            "keyfile": str(fpath),
            "pk_file": str(fpath) + ".pub",
        }

        enc_data = nacl.enc("blah", **kwargs)
        ret = nacl.dec(enc_data, **kwargs)
        assert isinstance(ret, bytes)
        assert ret == b"blah"
        salt.utils.files.remove(str(fpath) + ".pub")


def test_dec_sk_file(test_keygen):
    """
    test nacl.dec function
    with sk_file and pk_file set
    """
    with pytest.helpers.temp_file("test_dec_sk_file") as fpath:
        with salt.utils.files.fopen(fpath, "wb") as wfh:
            wfh.write(test_keygen["sk"])
        with salt.utils.files.fopen(str(fpath) + ".pub", "wb") as wfhpub:
            wfhpub.write(test_keygen["pk"])

        kwargs = {
            "opts": {"pki_dir": os.path.dirname(fpath)},
            "sk_file": str(fpath),
            "pk_file": str(fpath) + ".pub",
        }

        enc_data = nacl.enc("blah", **kwargs)
        ret = nacl.dec(enc_data, **kwargs)
        assert isinstance(ret, bytes)
        assert ret == b"blah"
        salt.utils.files.remove(str(fpath) + ".pub")
