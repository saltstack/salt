# -*- coding: utf-8 -*-
"""
Tests the localfs tokens interface.
"""
from __future__ import absolute_import, print_function, unicode_literals

import os

import salt.exceptions
import salt.tokens.localfs
import salt.utils.files
from tests.support.helpers import with_tempdir
from tests.support.mock import patch
from tests.support.unit import TestCase


class CalledWith(object):
    def __init__(self, func, called_with=None):
        self.func = func
        if called_with is None:
            self.called_with = []
        else:
            self.called_with = called_with

    def __call__(self, *args, **kwargs):
        self.called_with.append((args, kwargs))
        return self.func(*args, **kwargs)


class WriteTokenTest(TestCase):
    @with_tempdir()
    def test_write_token(self, tmpdir):
        """
        Validate tokens put in place with an atomic move
        """
        opts = {"token_dir": tmpdir}
        fopen = CalledWith(salt.utils.files.fopen)
        rename = CalledWith(os.rename)
        with patch("salt.utils.files.fopen", fopen), patch("os.rename", rename):
            tdata = salt.tokens.localfs.mk_token(opts, {})
        assert "token" in tdata
        t_path = os.path.join(tmpdir, tdata["token"])
        temp_t_path = "{}.tmp".format(t_path)
        assert len(fopen.called_with) == 1, len(fopen.called_with)
        assert fopen.called_with == [((temp_t_path, "w+b"), {})], fopen.called_with
        assert len(rename.called_with) == 1, len(rename.called_with)
        assert rename.called_with == [((temp_t_path, t_path), {})], rename.called_with


class TestLocalFS(TestCase):
    def setUp(self):
        # Default expected data
        self.expected_data = {"this": "is", "some": "token data"}

    @with_tempdir()
    def test_get_token_should_return_token_if_exists(self, tempdir):
        opts = {"token_dir": tempdir}
        tok = salt.tokens.localfs.mk_token(opts=opts, tdata=self.expected_data,)[
            "token"
        ]
        actual_data = salt.tokens.localfs.get_token(opts=opts, tok=tok)
        self.assertDictEqual(self.expected_data, actual_data)

    @with_tempdir()
    def test_get_token_should_raise_SaltDeserializationError_if_token_file_is_empty(
        self, tempdir
    ):
        opts = {"token_dir": tempdir}
        tok = salt.tokens.localfs.mk_token(opts=opts, tdata=self.expected_data,)[
            "token"
        ]
        with salt.utils.files.fopen(os.path.join(tempdir, tok), "w") as f:
            f.truncate()
        with self.assertRaises(salt.exceptions.SaltDeserializationError) as e:
            salt.tokens.localfs.get_token(opts=opts, tok=tok)

    @with_tempdir()
    def test_get_token_should_raise_SaltDeserializationError_if_token_file_is_malformed(
        self, tempdir
    ):
        opts = {"token_dir": tempdir}
        tok = salt.tokens.localfs.mk_token(opts=opts, tdata=self.expected_data,)[
            "token"
        ]
        with salt.utils.files.fopen(os.path.join(tempdir, tok), "w") as f:
            f.truncate()
            f.write("this is not valid msgpack data")
        with self.assertRaises(salt.exceptions.SaltDeserializationError) as e:
            salt.tokens.localfs.get_token(opts=opts, tok=tok)
