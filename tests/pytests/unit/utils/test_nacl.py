"""
    Unit tests for the salt.utils.nacl module
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

import pytest

import salt.utils.files
from tests.support.mock import patch

pytest.importorskip("nacl.public")
pytest.importorskip("nacl.secret")

import salt.utils.nacl as nacl

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]


def _nacl_enc_dec_sealedbox_subprocess(plain: str, kwargs: dict):
    """
    Run ``salt.utils.nacl`` sealed-box ``enc``/``dec`` in a clean interpreter.

    PyNaCl ``crypto_box_seal`` can segfault under pytest when salt-factories
    keeps asyncio and ZMQ threads alive in the same process (onedir/Linux).
    A short-lived child process avoids that interaction while still exercising
    the same Salt code paths.
    """
    payload = {"plain": plain, "kwargs": kwargs}
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".json", delete=False
    ) as tmp:
        json.dump(payload, tmp)
        tmp_path = tmp.name

    worker = r"""
import json, os, sys

def _cg(key, default="", *args, **kwargs):
    return default

os.environ.setdefault("ONEDIR_TESTRUN", "1")
os.chdir(sys.argv[2])

import salt.utils.nacl as nacl

nacl.__salt__ = {"config.get": _cg}
with open(sys.argv[1], encoding="utf-8") as fh:
    payload = json.load(fh)
plain = payload["plain"]
kwargs = payload["kwargs"]
enc_data = nacl.enc(plain, **kwargs)
dec_data = nacl.dec(enc_data, **kwargs)
sys.stdout.buffer.write(enc_data + b"\0" + dec_data)
"""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", worker, tmp_path, str(_REPO_ROOT)],
            cwd=str(_REPO_ROOT),
            check=True,
            capture_output=True,
            timeout=120,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    out = proc.stdout
    sep = out.index(b"\0")
    return out[:sep], out[sep + 1 :]


def _nacl_enc_sealedbox_subprocess(plain: str, kwargs: dict) -> bytes:
    enc_data, _dec = _nacl_enc_dec_sealedbox_subprocess(plain, kwargs)
    return enc_data


def _nacl_test_config_get(key, default="", *args, **kwargs):
    """
    Minimal stand-in for salt.modules.config.config.get.

    Importing ``salt.modules.config`` before PyNaCl sealed-box operations can
    segfault in some builds (e.g. onedir) due to native crypto init ordering.
    ``salt.utils.nacl`` only needs ``config.get("nacl.config", {})``-style
    merges for ``_get_config``; returning the provided default matches the
    empty-minion-config behavior these tests relied on.
    """
    return default


@pytest.fixture
def configure_loader_modules():
    return {
        nacl: {"__salt__": {"config.get": _nacl_test_config_get}},
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
        with salt.utils.files.fopen(str(fpath) + ".pub", "rb") as rfh:
            assert test_keygen["pk"] == rfh.read()
        salt.utils.files.remove(str(fpath) + ".pub")


def test_keygen_nonexistent_sk_file():
    """
    test nacl.keygen function
    with nonexistent/new sk_file
    """
    with pytest.helpers.temp_file("test_keygen_sk_file") as fpath:
        salt.utils.files.remove(str(fpath))
        ret = nacl.keygen(sk_file=str(fpath))
        assert f"saved sk_file:{fpath}  pk_file: {fpath}.pub" == ret
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

    Sealed-box ``enc`` is run in a subprocess: the same call segfaults in-process
    when pytest + salt-factories background threads are active (see
    ``_nacl_enc_sealedbox_subprocess``).
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
        ret = _nacl_enc_sealedbox_subprocess("blah", kwargs)
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

    Same subprocess isolation as ``test_enc_sk_file`` for sealed-box crypto.
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

        enc_data, ret = _nacl_enc_dec_sealedbox_subprocess("blah", kwargs)
        assert isinstance(enc_data, bytes)
        assert isinstance(ret, bytes)
        assert ret == b"blah"
        salt.utils.files.remove(str(fpath) + ".pub")
