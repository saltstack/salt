# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import os

import salt.utils.files
import salt.tokens.localfs

from tests.support.unit import TestCase, skipIf
from tests.support.helpers import with_tempdir
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch


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


@skipIf(NO_MOCK, NO_MOCK_REASON)
class WriteTokenTest(TestCase):

    @with_tempdir()
    def test_write_token(self, tmpdir):
        '''
        Validate tokens put in place with an atomic move
        '''
        opts = {
            'token_dir': tmpdir
        }
        fopen = CalledWith(salt.utils.files.fopen)
        rename = CalledWith(os.rename)
        with patch('salt.utils.files.fopen', fopen), patch('os.rename', rename):
            tdata = salt.tokens.localfs.mk_token(opts, {})
        assert 'token' in tdata
        t_path = os.path.join(tmpdir, tdata['token'])
        temp_t_path = '{}.tmp'.format(t_path)
        assert len(fopen.called_with) == 1, len(fopen.called_with)
        assert fopen.called_with == [
            ((temp_t_path, 'w+b'), {})
        ], fopen.called_with
        assert len(rename.called_with) == 1, len(rename.called_with)
        assert rename.called_with == [
            ((temp_t_path, t_path), {})
        ], rename.called_with
