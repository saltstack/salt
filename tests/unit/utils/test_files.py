# -*- coding: utf-8 -*-
'''
Unit Tests for functions located in salt.utils.files.py.
'''

# Import python libs
from __future__ import absolute_import
import os

# Import Salt libs
import salt.utils.files

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)


class FilesUtilTestCase(TestCase):
    '''
    Test case for files util.
    '''

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_safe_rm(self):
        with patch('os.remove') as os_remove_mock:
            salt.utils.files.safe_rm('dummy_tgt')
            self.assertTrue(os_remove_mock.called)

    @skipIf(os.path.exists('/tmp/no_way_this_is_a_file_nope.sh'), 'Test file exists! Skipping safe_rm_exceptions test!')
    def test_safe_rm_exceptions(self):
        error = False
        try:
            salt.utils.files.safe_rm('/tmp/no_way_this_is_a_file_nope.sh')
        except (IOError, OSError):
            error = True
        self.assertFalse(error, 'salt.utils.files.safe_rm raised exception when it should not have')
