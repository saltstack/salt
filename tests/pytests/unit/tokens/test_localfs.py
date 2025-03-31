"""
Tests the localfs tokens interface.
"""

import os

import pytest

import salt.exceptions
import salt.tokens.localfs
import salt.utils.files
from tests.support.mock import patch


class CalledWith:
    def __init__(self, func, called_with=None):
        self.func = func
        if called_with is None:
            self.called_with = []
        else:
            self.called_with = called_with

    def __call__(self, *args, **kwargs):
        self.called_with.append((args, kwargs))
        return self.func(*args, **kwargs)


@pytest.fixture
def expected_data():
    # Default expected data
    return {"this": "is", "some": "token data"}


def test_write_token(tmp_path):
    """
    Validate tokens put in place with an atomic move
    """
    opts = {"token_dir": str(tmp_path)}
    fopen = CalledWith(salt.utils.files.fopen)
    rename = CalledWith(os.rename)
    with patch("salt.utils.files.fopen", fopen), patch("os.rename", rename):
        tdata = salt.tokens.localfs.mk_token(opts, {})
    assert "token" in tdata
    t_path = os.path.join(str(tmp_path), tdata["token"])
    temp_t_path = f"{t_path}.tmp"
    assert len(fopen.called_with) == 1, len(fopen.called_with)
    assert fopen.called_with == [((temp_t_path, "w+b"), {})], fopen.called_with
    assert len(rename.called_with) == 1, len(rename.called_with)
    assert rename.called_with == [((temp_t_path, t_path), {})], rename.called_with


def test_get_token_should_return_token_if_exists(tmp_path, expected_data):
    opts = {"token_dir": str(tmp_path)}
    tok = salt.tokens.localfs.mk_token(
        opts=opts,
        tdata=expected_data,
    )["token"]
    actual_data = salt.tokens.localfs.get_token(opts=opts, tok=tok)
    assert expected_data == actual_data


def test_get_token_should_raise_SaltDeserializationError_if_token_file_is_empty(
    tmp_path, expected_data
):
    opts = {"token_dir": str(tmp_path)}
    tok = salt.tokens.localfs.mk_token(
        opts=opts,
        tdata=expected_data,
    )["token"]
    with salt.utils.files.fopen(os.path.join(str(tmp_path), tok), "w") as f:
        f.truncate()
    with pytest.raises(salt.exceptions.SaltDeserializationError) as e:
        salt.tokens.localfs.get_token(opts=opts, tok=tok)


def test_get_token_should_raise_SaltDeserializationError_if_token_file_is_malformed(
    tmp_path, expected_data
):
    opts = {"token_dir": str(tmp_path)}
    tok = salt.tokens.localfs.mk_token(
        opts=opts,
        tdata=expected_data,
    )["token"]
    with salt.utils.files.fopen(os.path.join(str(tmp_path), tok), "w") as f:
        f.truncate()
        f.write("this is not valid msgpack data")
    with pytest.raises(salt.exceptions.SaltDeserializationError) as e:
        salt.tokens.localfs.get_token(opts=opts, tok=tok)
