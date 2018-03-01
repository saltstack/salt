# -*- coding: utf-8 -*-
'''
Unit Tests for functions located in salt.utils.files.py.
'''

# Import python libs
from __future__ import absolute_import, unicode_literals, print_function
import os
import shutil
import tempfile

# Import Salt libs
import salt.utils.files

# Import Salt Testing libs
from tests.support.paths import TMP
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

    def test_safe_walk_symlink_recursion(self):
        tmp = tempfile.mkdtemp(dir=TMP)
        try:
            if os.stat(tmp).st_ino == 0:
                self.skipTest('inodes not supported in {0}'.format(tmp))
            os.mkdir(os.path.join(tmp, 'fax'))
            os.makedirs(os.path.join(tmp, 'foo/bar'))
            os.symlink('../..', os.path.join(tmp, 'foo/bar/baz'))
            os.symlink('foo', os.path.join(tmp, 'root'))
            expected = [
                (os.path.join(tmp, 'root'), ['bar'], []),
                (os.path.join(tmp, 'root/bar'), ['baz'], []),
                (os.path.join(tmp, 'root/bar/baz'), ['fax', 'foo', 'root'], []),
                (os.path.join(tmp, 'root/bar/baz/fax'), [], []),
            ]
            paths = []
            for root, dirs, names in salt.utils.files.safe_walk(os.path.join(tmp, 'root')):
                paths.append((root, sorted(dirs), names))
            if paths != expected:
                raise AssertionError(
                    '\n'.join(
                        ['got:'] + [repr(p) for p in paths] +
                        ['', 'expected:'] + [repr(p) for p in expected]
                    )
                )
        finally:
            shutil.rmtree(tmp)
