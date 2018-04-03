# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.utils.salt.utils.path.join_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import posixpath
import ntpath
import platform
import tempfile

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import patch, NO_MOCK, NO_MOCK_REASON

# Import Salt libs
import salt.utils.path
import salt.utils.platform
from salt.exceptions import CommandNotFoundError

# Import 3rd-party libs
from salt.ext import six


class PathJoinTestCase(TestCase):

    PLATFORM_FUNC = platform.system
    BUILTIN_MODULES = sys.builtin_module_names

    NIX_PATHS = (
        (('/', 'key'), '/key'),
        (('/etc/salt', '/etc/salt/pki'), '/etc/salt/etc/salt/pki'),
        (('/usr/local', '/etc/salt/pki'), '/usr/local/etc/salt/pki')

    )

    WIN_PATHS = (
        (('c:', 'temp', 'foo'), 'c:\\temp\\foo'),
        (('c:', r'\temp', r'\foo'), 'c:\\temp\\foo'),
        (('c:\\', r'\temp', r'\foo'), 'c:\\temp\\foo'),
        ((r'c:\\', r'\temp', r'\foo'), 'c:\\temp\\foo'),
        (('c:', r'\temp', r'\foo', 'bar'), 'c:\\temp\\foo\\bar'),
        (('c:', r'\temp', r'\foo\bar'), 'c:\\temp\\foo\\bar'),
    )

    @skipIf(True, 'Skipped until properly mocked')
    def test_nix_paths(self):
        if platform.system().lower() == "windows":
            self.skipTest(
                "Windows platform found. not running *nix salt.utils.path.join tests"
            )
        for idx, (parts, expected) in enumerate(self.NIX_PATHS):
            path = salt.utils.path.join(*parts)
            self.assertEqual(
                '{0}: {1}'.format(idx, path),
                '{0}: {1}'.format(idx, expected)
            )

    @skipIf(True, 'Skipped until properly mocked')
    def test_windows_paths(self):
        if platform.system().lower() != "windows":
            self.skipTest(
                'Non windows platform found. not running non patched os.path '
                'salt.utils.path.join tests'
            )

        for idx, (parts, expected) in enumerate(self.WIN_PATHS):
            path = salt.utils.path.join(*parts)
            self.assertEqual(
                '{0}: {1}'.format(idx, path),
                '{0}: {1}'.format(idx, expected)
            )

    @skipIf(True, 'Skipped until properly mocked')
    def test_windows_paths_patched_path_module(self):
        if platform.system().lower() == "windows":
            self.skipTest(
                'Windows platform found. not running patched os.path '
                'salt.utils.path.join tests'
            )

        self.__patch_path()

        for idx, (parts, expected) in enumerate(self.WIN_PATHS):
            path = salt.utils.path.join(*parts)
            self.assertEqual(
                '{0}: {1}'.format(idx, path),
                '{0}: {1}'.format(idx, expected)
            )

        self.__unpatch_path()

    @skipIf(salt.utils.platform.is_windows(), '*nix-only test')
    def test_mixed_unicode_and_binary(self):
        '''
        This tests joining paths that contain a mix of components with unicode
        strings and non-unicode strings with the unicode characters as binary.

        This is no longer something we need to concern ourselves with in
        Python 3, but the test should nonetheless pass on Python 3. Really what
        we're testing here is that we don't get a UnicodeDecodeError when
        running on Python 2.
        '''
        a = u'/foo/bar'
        b = 'Д'
        expected = u'/foo/bar/\u0414'
        actual = salt.utils.path.join(a, b)
        self.assertEqual(actual, expected)

    def __patch_path(self):
        import imp
        modules = list(self.BUILTIN_MODULES[:])
        modules.pop(modules.index('posix'))
        modules.append('nt')

        code = """'''Salt unittest loaded NT module'''"""
        module = imp.new_module('nt')
        six.exec_(code, module.__dict__)
        sys.modules['nt'] = module

        sys.builtin_module_names = modules
        platform.system = lambda: "windows"

        for module in (ntpath, os, os.path, tempfile):
            reload(module)

    def __unpatch_path(self):
        del sys.modules['nt']
        sys.builtin_module_names = self.BUILTIN_MODULES[:]
        platform.system = self.PLATFORM_FUNC

        for module in (posixpath, os, os.path, tempfile, platform):
            reload(module)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PathTestCase(TestCase):
    def test_which_bin(self):
        ret = salt.utils.path.which_bin('str')
        self.assertIs(None, ret)

        test_exes = ['ls', 'echo']
        with patch('salt.utils.path.which', return_value='/tmp/dummy_path'):
            ret = salt.utils.path.which_bin(test_exes)
            self.assertEqual(ret, '/tmp/dummy_path')

            ret = salt.utils.path.which_bin([])
            self.assertIs(None, ret)

        with patch('salt.utils.path.which', return_value=''):
            ret = salt.utils.path.which_bin(test_exes)
            self.assertIs(None, ret)

    def test_sanitize_win_path(self):
        p = '\\windows\\system'
        self.assertEqual(salt.utils.path.sanitize_win_path('\\windows\\system'), '\\windows\\system')
        self.assertEqual(salt.utils.path.sanitize_win_path('\\bo:g|us\\p?at*h>'), '\\bo_g_us\\p_at_h_')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_check_or_die(self):
        self.assertRaises(CommandNotFoundError, salt.utils.path.check_or_die, None)

        with patch('salt.utils.path.which', return_value=False):
            self.assertRaises(CommandNotFoundError, salt.utils.path.check_or_die, 'FAKE COMMAND')

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_join(self):
        with patch('salt.utils.platform.is_windows', return_value=False) as is_windows_mock:
            self.assertFalse(is_windows_mock.return_value)
            expected_path = os.path.join(os.sep + 'a', 'b', 'c', 'd')
            ret = salt.utils.path.join('/a/b/c', 'd')
            self.assertEqual(ret, expected_path)
