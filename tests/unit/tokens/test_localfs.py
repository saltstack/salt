# -*- coding: utf-8 -*-
'''
Tests the localfs tokens interface.
'''
from __future__ import absolute_import, print_function, unicode_literals

import os
import tempfile
import unittest

import salt.exceptions
import salt.tokens.localfs as localfs
from tests.support.helpers import with_tempdir


class TestLocalFS(unittest.TestCase):
    def setUp(self):
        # Default expected data
        self.expected_data = {'this': 'is', 'some': 'token data'}

    @with_tempdir()
    def test_get_token_should_return_token_if_exists(self, tempdir):
        opts = {'token_dir': tempdir}
        tok = localfs.mk_token(
            opts=opts,
            tdata=self.expected_data,
        )['token']
        actual_data = localfs.get_token(opts=opts, tok=tok)
        self.assertDictEqual(self.expected_data, actual_data)

    @with_tempdir()
    def test_get_token_should_raise_SaltDeserializationError_if_token_file_is_empty(self, tempdir):
        opts = {'token_dir': tempdir}
        tok = localfs.mk_token(
            opts=opts,
            tdata=self.expected_data,
        )['token']
        with open(os.path.join(tempdir, tok), 'w') as f:
            f.truncate()
        with self.assertRaises(salt.exceptions.SaltDeserializationError) as e:
            localfs.get_token(opts=opts, tok=tok)

    @with_tempdir()
    def test_get_token_should_raise_SaltDeserializationError_if_token_file_is_malformed(self, tempdir):
        opts = {'token_dir': tempdir}
        tok = localfs.mk_token(
            opts=opts,
            tdata=self.expected_data,
        )['token']
        with open(os.path.join(tempdir, tok), 'w') as f:
            f.truncate()
            f.write('this is not valid msgpack data')
        with self.assertRaises(salt.exceptions.SaltDeserializationError) as e:
            localfs.get_token(opts=opts, tok=tok)
