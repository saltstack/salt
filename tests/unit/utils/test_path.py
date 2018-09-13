# -*- coding: utf-8 -*-
'''
Tests for salt.utils.path
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
import salt.syspaths
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


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestWhich(TestCase):
    '''
    Tests salt.utils.path.which function to ensure that it returns True as
    expected.
    '''

    # The mock patch below will make sure that ALL calls to the which function
    # returns None
    def test_missing_binary_in_linux(self):
        with patch('salt.utils.path.which', lambda exe: None):
            self.assertTrue(
                salt.utils.path.which('this-binary-does-not-exist') is None
            )

    # The mock patch below will make sure that ALL calls to the which function
    # return whatever is sent to it
    def test_existing_binary_in_linux(self):
        with patch('salt.utils.path.which', lambda exe: exe):
            self.assertTrue(salt.utils.path.which('this-binary-exists-under-linux'))

    def test_existing_binary_in_windows(self):
        with patch('os.access') as osaccess:
            # We define the side_effect attribute on the mocked object in order to
            # specify which calls return which values. First call to os.access
            # returns X, the second Y, the third Z, etc...
            osaccess.side_effect = [
                # The first os.access should return False(the abspath one)
                False,
                # The second, iterating through $PATH, should also return False,
                # still checking for Linux
                False,
                # We will now also return False once so we get a .EXE back from
                # the function, see PATHEXT below.
                False,
                # Lastly return True, this is the windows check.
                True
            ]
            # Let's patch os.environ to provide a custom PATH variable
            with patch.dict(os.environ, {'PATH': os.sep + 'bin',
                                         'PATHEXT': '.COM;.EXE;.BAT;.CMD'}):
                # Let's also patch is_windows to return True
                with patch('salt.utils.platform.is_windows', lambda: True):
                    with patch('os.path.isfile', lambda x: True):
                        self.assertEqual(
                            salt.utils.path.which('this-binary-exists-under-windows'),
                            os.path.join(os.sep + 'bin', 'this-binary-exists-under-windows.EXE')
                        )

    def test_missing_binary_in_windows(self):
        with patch('os.access') as osaccess:
            osaccess.side_effect = [
                # The first os.access should return False(the abspath one)
                False,
                # The second, iterating through $PATH, should also return False,
                # still checking for Linux
                # which() will add 4 extra paths to the given one, os.access will
                # be called 5 times
                False, False, False, False, False
            ]
            # Let's patch os.environ to provide a custom PATH variable
            with patch.dict(os.environ, {'PATH': os.sep + 'bin'}):
                # Let's also patch is_widows to return True
                with patch('salt.utils.platform.is_windows', lambda: True):
                    self.assertEqual(
                        # Since we're passing the .exe suffix, the last True above
                        # will not matter. The result will be None
                        salt.utils.path.which('this-binary-is-missing-in-windows.exe'),
                        None
                    )

    def test_existing_binary_in_windows_pathext(self):
        with patch('os.access') as osaccess:
            # We define the side_effect attribute on the mocked object in order to
            # specify which calls return which values. First call to os.access
            # returns X, the second Y, the third Z, etc...
            osaccess.side_effect = [
                # The first os.access should return False(the abspath one)
                False,
                # The second, iterating through $PATH, should also return False,
                # still checking for Linux
                False,
                # We will now also return False 3 times so we get a .CMD back from
                # the function, see PATHEXT below.
                # Lastly return True, this is the windows check.
                False, False, False,
                True
            ]
            # Let's patch os.environ to provide a custom PATH variable
            with patch.dict(os.environ, {'PATH': os.sep + 'bin',
                                         'PATHEXT': '.COM;.EXE;.BAT;.CMD;.VBS;'
                                         '.VBE;.JS;.JSE;.WSF;.WSH;.MSC;.PY'}):
                # Let's also patch is_windows to return True
                with patch('salt.utils.platform.is_windows', lambda: True):
                    with patch('os.path.isfile', lambda x: True):
                        self.assertEqual(
                            salt.utils.path.which('this-binary-exists-under-windows'),
                            os.path.join(os.sep + 'bin', 'this-binary-exists-under-windows.CMD')
                        )


@skipIf(salt.utils.platform.is_windows(), '*nix-only test')
class PrependRootDirTestCase(TestCase):
    '''
    Test salt.utils.path.prepend_root_dir
    '''

    DEFAULT_ROOT_DIR = salt.syspaths.ROOT_DIR
    CUSTOM_ROOT_DIR = '/mock/root'

    ABSOLUTE_PATH = '/an/absolute/path'
    RELATIVE_PATH = 'a/relative/path'

    CURRENT_USER_HOME = '~/.salt'
    ROOT_USER_HOME = '~root/.salt'

    ABSOLUTE_GLOB_PATH = '/an/absolute/glob*'
    RELATIVE_GLOB_PATH = 'a/relative/glob/*'

    CURRENT_USER_HOME_GLOB_PATH = '~/.salt/*.conf'
    ROOT_USER_HOME_GLOB_PATH = '~root/.salt/*.conf'

    ## Test with the default root_dir option

    def test_absolute_path_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.ABSOLUTE_PATH),
            salt.utils.path.join(
                self.DEFAULT_ROOT_DIR,
                self.ABSOLUTE_PATH))

    def test_relative_path_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.RELATIVE_PATH),
            salt.utils.path.join(
                self.DEFAULT_ROOT_DIR,
                self.RELATIVE_PATH))

    def test_current_user_home_path_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.CURRENT_USER_HOME),
            salt.utils.path.join(
                self.DEFAULT_ROOT_DIR,
                self.CURRENT_USER_HOME))

    def test_root_user_home_path_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.ROOT_USER_HOME),
            salt.utils.path.join(
                self.DEFAULT_ROOT_DIR,
                self.ROOT_USER_HOME))

    def test_absolute_glob_path_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.ABSOLUTE_GLOB_PATH),
            salt.utils.path.join(
                self.DEFAULT_ROOT_DIR,
                self.ABSOLUTE_GLOB_PATH))

    def test_relative_glob_path_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.RELATIVE_GLOB_PATH),
            salt.utils.path.join(
                self.DEFAULT_ROOT_DIR,
                self.RELATIVE_GLOB_PATH))

    def test_current_user_home_with_glob_path_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.CURRENT_USER_HOME_GLOB_PATH),
            salt.utils.path.join(
                self.DEFAULT_ROOT_DIR,
                self.CURRENT_USER_HOME_GLOB_PATH))

    def test_root_user_home_with_glob_path_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.ROOT_USER_HOME_GLOB_PATH),
            salt.utils.path.join(
                self.DEFAULT_ROOT_DIR,
                self.ROOT_USER_HOME_GLOB_PATH))

    def test_file_scheme_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir('file://' + self.ABSOLUTE_PATH),
            salt.utils.path.join(
                self.DEFAULT_ROOT_DIR,
                'file:',
                self.ABSOLUTE_PATH))

    ## Test with a custom root_dir option

    def test_absolute_path_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.ABSOLUTE_PATH,
                                             self.CUSTOM_ROOT_DIR),
            salt.utils.path.join(
                self.CUSTOM_ROOT_DIR,
                self.ABSOLUTE_PATH))

    def test_relative_path_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.RELATIVE_PATH,
                                             self.CUSTOM_ROOT_DIR),
            salt.utils.path.join(
                self.CUSTOM_ROOT_DIR,
                self.RELATIVE_PATH))

    def test_current_user_home_path_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.CURRENT_USER_HOME,
                                             self.CUSTOM_ROOT_DIR),
            salt.utils.path.join(
                self.CUSTOM_ROOT_DIR,
                self.CURRENT_USER_HOME))

    def test_root_user_home_path_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.ROOT_USER_HOME,
                                             self.CUSTOM_ROOT_DIR),
            salt.utils.path.join(
                self.CUSTOM_ROOT_DIR,
                self.ROOT_USER_HOME))

    def test_absolute_glob_path_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.ABSOLUTE_GLOB_PATH,
                                             self.CUSTOM_ROOT_DIR),
            salt.utils.path.join(
                self.CUSTOM_ROOT_DIR,
                self.ABSOLUTE_GLOB_PATH))

    def test_relative_glob_path_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.RELATIVE_GLOB_PATH,
                                             self.CUSTOM_ROOT_DIR),
            salt.utils.path.join(
                self.CUSTOM_ROOT_DIR,
                self.RELATIVE_GLOB_PATH))

    def test_current_user_home_with_glob_path_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.CURRENT_USER_HOME_GLOB_PATH,
                                             self.CUSTOM_ROOT_DIR),
            salt.utils.path.join(
                self.CUSTOM_ROOT_DIR,
                self.CURRENT_USER_HOME_GLOB_PATH))

    def test_root_user_home_with_glob_path_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir(self.ROOT_USER_HOME_GLOB_PATH,
                                             self.CUSTOM_ROOT_DIR),
            salt.utils.path.join(
                self.CUSTOM_ROOT_DIR,
                self.ROOT_USER_HOME_GLOB_PATH))

    def test_file_scheme_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.prepend_root_dir('file://' + self.ABSOLUTE_PATH,
                                             self.CUSTOM_ROOT_DIR),
            salt.utils.path.join(
                self.CUSTOM_ROOT_DIR,
                'file:',
                self.ABSOLUTE_PATH))


@skipIf(salt.utils.platform.is_windows(), '*nix-only test')
class ExpandPathTestCase(TestCase):
    '''
    Test salt.utils.path.expand_path
    '''

    DEFAULT_ROOT_DIR = salt.syspaths.ROOT_DIR
    CUSTOM_ROOT_DIR = '/mock/root'

    ABSOLUTE_PATH = '/an/absolute/path'
    RELATIVE_PATH = 'a/relative/path'

    CURRENT_USER_HOME = '~/'
    ABSOLUTE_CURRENT_USER_HOME = '/mock/home/user'

    ROOT_USER_HOME = '~root/'
    ABSOLUTE_ROOT_USER_HOME = '/mock/root'

    ABSOLUTE_GLOB_PATH = '/an/absolute/glob*'
    RELATIVE_GLOB_PATH = 'a/relative/glob/*'

    CURRENT_USER_HOME_GLOB_PATH = '~/.salt/*.conf'
    ABSOLUTE_CURRENT_USER_HOME_GLOB_PATH = '/mock/home/user/.salt/*.conf'

    ROOT_USER_HOME_GLOB_PATH = '~root/.salt/*.conf'
    ABSOLUTE_ROOT_USER_HOME_GLOB_PATH = '/mock/root/.salt/*.conf'

    ## Test with the default root_dir option

    def test_absolute_path_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.expand_path(self.ABSOLUTE_PATH),
            salt.utils.path.join(
                self.DEFAULT_ROOT_DIR,
                self.ABSOLUTE_PATH))

    def test_relative_path_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.expand_path(self.RELATIVE_PATH),
            salt.utils.path.join(
                self.DEFAULT_ROOT_DIR,
                self.RELATIVE_PATH))

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_current_user_home_path_with_default_root_dir(self):
        with patch('os.path.expanduser', return_value=self.ABSOLUTE_CURRENT_USER_HOME):
            self.assertEqual(
                salt.utils.path.expand_path(self.CURRENT_USER_HOME),
                self.ABSOLUTE_CURRENT_USER_HOME)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_root_user_home_path_with_default_root_dir(self):
        with patch('os.path.expanduser', return_value=self.ABSOLUTE_ROOT_USER_HOME):
            self.assertEqual(
                salt.utils.path.expand_path(self.ROOT_USER_HOME),
                self.ABSOLUTE_ROOT_USER_HOME)

    def test_absolute_glob_path_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.expand_path(self.ABSOLUTE_GLOB_PATH),
            salt.utils.path.join(
                self.DEFAULT_ROOT_DIR,
                self.ABSOLUTE_GLOB_PATH))

    def test_relative_glob_path_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.expand_path(self.RELATIVE_GLOB_PATH),
            salt.utils.path.join(
                self.DEFAULT_ROOT_DIR,
                self.RELATIVE_GLOB_PATH))

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_current_user_home_with_glob_path_with_default_root_dir(self):
        with patch('os.path.expanduser', return_value=self.ABSOLUTE_CURRENT_USER_HOME_GLOB_PATH):
            self.assertEqual(
                salt.utils.path.expand_path(self.CURRENT_USER_HOME_GLOB_PATH),
                self.ABSOLUTE_CURRENT_USER_HOME_GLOB_PATH)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_root_user_home_with_glob_path_with_default_root_dir(self):
        with patch('os.path.expanduser', return_value=self.ABSOLUTE_ROOT_USER_HOME_GLOB_PATH):
            self.assertEqual(
                salt.utils.path.expand_path(self.ROOT_USER_HOME_GLOB_PATH),
                self.ABSOLUTE_ROOT_USER_HOME_GLOB_PATH)

    def test_file_scheme_with_default_root_dir(self):
        self.assertEqual(
            salt.utils.path.expand_path('file://' + self.ABSOLUTE_GLOB_PATH),
            'file://' + self.ABSOLUTE_GLOB_PATH)

    ## Test with a custom root_dir option

    def test_absolute_path_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.expand_path(self.ABSOLUTE_PATH,
                                        self.CUSTOM_ROOT_DIR),
            salt.utils.path.join(
                self.CUSTOM_ROOT_DIR,
                self.ABSOLUTE_PATH))

    def test_relative_path_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.expand_path(self.RELATIVE_PATH,
                                        self.CUSTOM_ROOT_DIR),
            salt.utils.path.join(
                self.CUSTOM_ROOT_DIR,
                self.RELATIVE_PATH))

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_current_user_home_path_with_custom_root_dir(self):
        with patch('os.path.expanduser', return_value=self.ABSOLUTE_CURRENT_USER_HOME):
            self.assertEqual(
                salt.utils.path.expand_path(self.CURRENT_USER_HOME,
                                            self.CUSTOM_ROOT_DIR),
                self.ABSOLUTE_CURRENT_USER_HOME)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_root_user_home_path_with_custom_root_dir(self):
        with patch('os.path.expanduser', return_value=self.ABSOLUTE_ROOT_USER_HOME):
            self.assertEqual(
                salt.utils.path.expand_path(self.ROOT_USER_HOME,
                                            self.CUSTOM_ROOT_DIR),
                self.ABSOLUTE_ROOT_USER_HOME)

    def test_absolute_glob_path_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.expand_path(self.ABSOLUTE_GLOB_PATH,
                                        self.CUSTOM_ROOT_DIR),
            salt.utils.path.join(
                self.CUSTOM_ROOT_DIR,
                self.ABSOLUTE_GLOB_PATH))

    def test_relative_glob_path_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.expand_path(self.RELATIVE_GLOB_PATH,
                                        self.CUSTOM_ROOT_DIR),
            salt.utils.path.join(
                self.CUSTOM_ROOT_DIR,
                self.RELATIVE_GLOB_PATH))

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_current_user_home_with_glob_path_with_custom_root_dir(self):
        with patch('os.path.expanduser', return_value=self.ABSOLUTE_CURRENT_USER_HOME_GLOB_PATH):
            self.assertEqual(
                salt.utils.path.expand_path(self.CURRENT_USER_HOME_GLOB_PATH,
                                            self.CUSTOM_ROOT_DIR),
                self.ABSOLUTE_CURRENT_USER_HOME_GLOB_PATH)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_root_user_home_with_glob_path_with_custom_root_dir(self):
        with patch('os.path.expanduser', return_value=self.ABSOLUTE_ROOT_USER_HOME_GLOB_PATH):
            self.assertEqual(
                salt.utils.path.expand_path(self.ROOT_USER_HOME_GLOB_PATH,
                                            self.CUSTOM_ROOT_DIR),
                self.ABSOLUTE_ROOT_USER_HOME_GLOB_PATH)

    def test_file_scheme_with_custom_root_dir(self):
        self.assertEqual(
            salt.utils.path.expand_path('file://' + self.ABSOLUTE_GLOB_PATH,
                                        self.CUSTOM_ROOT_DIR),
            'file://' + self.ABSOLUTE_GLOB_PATH)
