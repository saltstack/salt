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
from salt.ext import six

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

    @skipIf(not six.PY3, 'This test only applies to Python 3')
    def test_fopen_with_disallowed_fds(self):
        '''
        This is safe to have as a unit test since we aren't going to actually
        try to read or write. We want to ensure that we are raising a
        TypeError. Python 3's open() builtin will treat the booleans as file
        descriptor numbers and try to open stdin/stdout. We also want to test
        fd 2 which is stderr.
        '''
        for invalid_fn in (False, True, 0, 1, 2):
            try:
                with salt.utils.files.fopen(invalid_fn):
                    pass
            except TypeError:
                # This is expected. We aren't using an assertRaises here
                # because we want to ensure that if we did somehow open the
                # filehandle, that it doesn't remain open.
                pass
            else:
                # We probably won't even get this far if we actually opened
                # stdin/stdout as a file descriptor. It is likely to cause the
                # integration suite to die since, news flash, closing
                # stdin/stdout/stderr is usually not a wise thing to do in the
                # middle of a program's execution.
                self.fail(
                    'fopen() should have been prevented from opening a file '
                    'using {0} as the filename'.format(invalid_fn)
                )
