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
from tests.support.helpers import destructiveTest

# Import Salt libs
import salt.utils.compat
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
            salt.utils.compat.reload(module)

    def __unpatch_path(self):
        del sys.modules['nt']
        sys.builtin_module_names = self.BUILTIN_MODULES[:]
        platform.system = self.PLATFORM_FUNC

        for module in (posixpath, os, os.path, tempfile, platform):
            salt.utils.compat.reload(module)


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


# @skipIf(NO_MOCK, NO_MOCK_REASON)
# @destructiveTest
class TestPath(TestCase):
    def setUp(self):
        self.working_dir = tempfile.TemporaryDirectory().name
        if not os.path.exists(self.working_dir):
            os.mkdir(self.working_dir)
        self.dir_exist = os.path.join(self.working_dir, 'dir_exist')
        if not os.path.exists(self.dir_exist):
            os.mkdir(self.dir_exist)
        self.dir_absent = os.path.join(self.working_dir, 'dir_absent')
        self.file_exist = os.path.join(self.dir_exist, 'file_exist.txt')
        with open(self.file_exist, 'a'):
            os.utime(self.file_exist, None)
        self.file_absent = os.path.join(self.dir_exist, 'file_absent.txt')

    def tearDown(self):
        if os.path.exists(self.file_exist):
            os.remove(self.file_exist)
        if os.path.exists(self.file_absent):
            os.remove(self.file_absent)
        if os.path.exists(self.dir_exist):
            os.rmdir(self.dir_exist)
        if os.path.exists(self.dir_absent):
            os.rmdir(self.dir_absent)
        if os.path.exists(self.working_dir):
            os.rmdir(self.working_dir)

        del self.dir_exist
        del self.dir_absent
        del self.file_exist
        del self.file_absent
        del self.working_dir

    def test_path_is_absolute(self):
        self.assertTrue(salt.utils.path.is_absolute(self.dir_exist))

    def test_path_is_not_absolute(self):
        self.assertFalse(salt.utils.path.is_absolute('test'))

    def test_path_exist(self):
        self.assertTrue(salt.utils.path.exist(self.dir_exist))

    def test_path_not_exist(self):
        self.assertFalse(salt.utils.path.exist(self.dir_absent))

    def test_path_is_dir(self):
        self.assertTrue(salt.utils.path.is_dir(self.dir_exist))

    def test_path_is_not_dir(self):
        self.assertFalse(salt.utils.path.is_dir(self.dir_absent))
        self.assertFalse(salt.utils.path.is_dir(self.file_exist))

    def test_path_is_file(self):
        self.assertTrue(salt.utils.path.is_file(self.file_exist))

    def test_path_is_not_file(self):
        self.assertFalse(salt.utils.path.is_file(self.dir_exist))
        self.assertFalse(salt.utils.path.is_file(self.file_absent))

    def test_path_dir_is_present(self):
        self.assertTrue(salt.utils.path.dir_is_present(self.dir_exist))
        self.assertTrue(salt.utils.path.dir_is_present(self.dir_absent))
        self.assertTrue(os.path.exists(self.dir_absent))

    def test_path_file_is_present(self):
        self.assertTrue(salt.utils.path.file_is_present(self.file_exist))
        self.assertTrue(salt.utils.path.file_is_present(self.file_absent))
        self.assertTrue(os.path.exists(self.file_absent))

    def test_path_random_tmp_file(self):
        tmp_file = salt.utils.path.random_tmp_file(self.dir_exist)
        self.assertTrue(os.path.exists(tmp_file))
        os.remove(tmp_file)


# @skipIf(NO_MOCK, NO_MOCK_REASON)
# @destructiveTest
class path_stats_TestCase(TestCase):

    def setUp(self):
        self.init_group = {'name': salt.utils.group.gid_to_group(os.getegid()), 'id': os.getegid()}
        self.init_user = {'name': salt.utils.user.uid_to_user(os.geteuid()), 'id': os.geteuid()}
        self.group = {'name': 'group1', 'id': 1331}
        self.user = {'name': 'user1', 'id': 1221}

        # Configure the system.
        os.system('groupadd -g {} {}'.format(self.group['id'], self.group['name']))
        os.system('useradd -g {} -G {} -u {} {}'.format(self.group['id'], self.group['name'], self.user['id'], self.user['name']))

        self.working_dir = tempfile.TemporaryDirectory().name
        self.file_present = os.path.join(self.working_dir, 'file_present')
        self.dir_one_present = os.path.join(self.working_dir, 'dir_one_present')
        self.file_one_present = os.path.join(self.dir_one_present, 'file_one_present')
        self.link_file_one_present = os.path.join(self.working_dir, 'link_file_one_present')
        self.dir_two_present = os.path.join(self.working_dir, 'dir_two_present')
        self.link_dir_two_present = os.path.join(self.working_dir, 'link_dir_two_present')
        self.file_two_present = os.path.join(self.dir_two_present, 'file_two_present')
        self.dir_tree_present = os.path.join(self.working_dir, 'dir_tree_present')
        self.file_tree_absent = os.path.join(self.dir_tree_present, 'file_tree_absent')
        self.link_file_tree_absent = os.path.join(self.working_dir, 'link_file_tree_absent')
        self.dir_four_absent = os.path.join(self.working_dir, 'dir_four_absent')
        self.link_dir_four_absent = os.path.join(self.working_dir, 'link_dir_four_absent')

        self.other_dir = tempfile.TemporaryDirectory().name
        self.link_other_dir_present = os.path.join(self.working_dir, 'link_other_dir_present')
        self.other_file_present = os.path.join(self.other_dir, 'other_file_present')
        self.link_other_file_present = os.path.join(self.working_dir, 'link_other_file_present')

        salt.utils.path.dir_is_present(self.working_dir)
        salt.utils.path.file_is_present(self.file_present)
        salt.utils.path.dir_is_present(self.dir_one_present)
        salt.utils.path.file_is_present(self.file_one_present)
        salt.utils.path.set_link(self.file_one_present, self.link_file_one_present)
        salt.utils.path.dir_is_present(self.dir_two_present)
        salt.utils.path.set_link(self.dir_two_present, self.link_dir_two_present)
        salt.utils.path.file_is_present(self.file_two_present)
        salt.utils.path.dir_is_present(self.dir_tree_present)
        salt.utils.path.set_link(self.file_tree_absent, self.link_file_tree_absent)
        salt.utils.path.set_link(self.dir_four_absent, self.link_dir_four_absent)

        salt.utils.path.dir_is_present(self.other_dir)
        salt.utils.path.set_link(self.other_dir, self.link_other_dir_present)
        salt.utils.path.file_is_present(self.other_file_present)
        salt.utils.path.set_link(self.other_file_present, self.link_other_file_present)

    def tearDown(self):
        # Set the current Execution group to the initial group.
        os.seteuid(self.init_user['id'])
        os.setegid(self.init_group['id'])

        # Remove users and groups used to test
        os.system('userdel -fr {}'.format(self.user['name']))
        os.system('groupdel {}'.format(self.group['name']))

        del self.group
        del self.user
        del self.init_user
        del self.init_group

        salt.utils.path.file_is_absent(self.link_other_file_present)
        salt.utils.path.file_is_absent(self.other_file_present)
        salt.utils.path.file_is_absent(self.link_other_dir_present)
        salt.utils.path.dir_is_absent(self.other_dir)

        salt.utils.path.file_is_absent(self.link_dir_four_absent)
        salt.utils.path.file_is_absent(self.link_file_tree_absent)
        salt.utils.path.dir_is_absent(self.dir_tree_present)
        salt.utils.path.file_is_absent(self.file_two_present)
        salt.utils.path.file_is_absent(self.link_dir_two_present)
        salt.utils.path.dir_is_absent(self.dir_two_present)
        salt.utils.path.file_is_absent(self.link_file_one_present)
        salt.utils.path.file_is_absent(self.file_one_present)
        salt.utils.path.dir_is_absent(self.dir_one_present)
        salt.utils.path.file_is_absent(self.file_present)
        salt.utils.path.dir_is_absent(self.working_dir)

        del self.link_other_file_present
        del self.other_file_present
        del self.link_other_dir_present
        del self.other_dir

        del self.link_dir_four_absent
        del self.dir_four_absent
        del self.link_file_tree_absent
        del self.file_tree_absent
        del self.dir_tree_present
        del self.file_two_present
        del self.link_dir_two_present
        del self.dir_two_present
        del self.link_file_one_present
        del self.file_one_present
        del self.dir_one_present
        del self.file_present
        del self.working_dir

    #  FUNC: get_user
    ##################################################
    def test_get_user_file(self):
        self.assertEqual(self.init_user['name'], salt.utils.path.get_user(self.file_present))

    def test_get_user_dir(self):
        self.assertEqual(self.init_user['name'], salt.utils.path.get_user(self.dir_tree_present))

    def test_get_user_symlink(self):
        self.assertEqual(self.init_user['name'], salt.utils.path.get_user(self.link_other_file_present))

    #  FUNC: get_uid
    ##################################################
    def test_get_uid_file(self):
        self.assertEqual(self.init_user['id'], salt.utils.path.get_uid(self.file_present))

    def test_get_uid_dir(self):
        self.assertEqual(self.init_user['id'], salt.utils.path.get_uid(self.dir_tree_present))

    def test_get_uid_symlink(self):
        self.assertEqual(self.init_user['id'], salt.utils.path.get_uid(self.link_other_file_present))

    #  FUNC: set_user
    ##################################################
    def test_set_user_file(self):
        self.assertTrue(salt.utils.path.set_user(self.file_present, self.user['name']))
        self.assertEqual(self.user['name'], salt.utils.path.get_user(self.file_present))

    def test_set_user_dir(self):
        self.assertTrue(salt.utils.path.set_user(self.dir_tree_present, self.user['name']))
        self.assertEqual(self.user['name'], salt.utils.path.get_user(self.dir_tree_present))

    def test_set_user_symlink(self):
        self.assertFalse(salt.utils.path.set_user(self.link_other_file_present, self.user['name']))

    #  FUNC: get_group
    ##################################################
    def test_get_group_file(self):
        self.assertEqual(self.init_group['name'], salt.utils.path.get_group(self.file_present))

    def test_get_group_dir(self):
        self.assertEqual(self.init_group['name'], salt.utils.path.get_group(self.dir_tree_present))

    def test_get_group_symlink(self):
        self.assertEqual(self.init_group['name'], salt.utils.path.get_group(self.link_other_file_present))

    #  FUNC: get_gid
    ##################################################
    def test_get_gid_file(self):
        self.assertEqual(self.init_group['id'], salt.utils.path.get_gid(self.file_present))

    def test_get_gid_dir(self):
        self.assertEqual(self.init_group['id'], salt.utils.path.get_gid(self.dir_tree_present))

    def test_get_gid_symlink(self):
        self.assertEqual(self.init_group['id'], salt.utils.path.get_gid(self.link_other_file_present))

    #  FUNC: set_group
    ##################################################
    def test_set_group_file(self):
        self.assertTrue(salt.utils.path.set_group(self.file_present, self.group['name']))
        self.assertEqual(self.group['name'], salt.utils.path.get_group(self.file_present))

    def test_set_group_dir(self):
        self.assertTrue(salt.utils.path.set_group(self.dir_tree_present, self.group['name']))
        self.assertEqual(self.group['name'], salt.utils.path.get_group(self.dir_tree_present))

    def test_set_group_symlink(self):
        self.assertFalse(salt.utils.path.set_group(self.link_other_file_present, self.group['name']))

    #  FUNC: get_type
    ##################################################
    def test_get_type_file(self):
        self.assertEqual('file', salt.utils.path.get_type(self.file_present))

    def test_get_type_dir(self):
        self.assertEqual('dir', salt.utils.path.get_type(self.dir_tree_present))

    def test_get_type_symlink_to_file(self):
        self.assertEqual('link', salt.utils.path.get_type(self.link_other_file_present))

    def test_get_type_symlink_to_dir(self):
        self.assertEqual('link', salt.utils.path.get_type(self.link_other_dir_present))

    #  FUNC: set_perms
    ##################################################
    ### For files.
    def test_set_perms_file_no_changes(self):
        wanted_ret = {
            self.file_present: {
                'user': salt.utils.path.get_user(self.file_present),
                'group': salt.utils.path.get_group(self.file_present),
                'mode': salt.utils.path.get_mode(self.file_present)
            }
        }
        self.assertEqual(wanted_ret, salt.utils.path.set_perms(self.file_present))

    def test_set_perms_file_change_user(self):
        wanted_ret = {
            self.file_present: {
                'user': self.user['name'],
                'group': salt.utils.path.get_group(self.file_present),
                'mode': salt.utils.path.get_mode(self.file_present)
            }
        }
        self.assertEqual(wanted_ret, salt.utils.path.set_perms(self.file_present,
                                                               user=self.user['name']))

    def test_set_perms_file_change_group(self):
        wanted_ret = {
            self.file_present: {
                'user': salt.utils.path.get_user(self.file_present),
                'group': self.group['name'],
                'mode': salt.utils.path.get_mode(self.file_present)
            }
        }
        self.assertEqual(wanted_ret, salt.utils.path.set_perms(self.file_present,
                                                               group=self.group['name']))

    def test_set_perms_file_change_mode(self):
        wanted_ret = {
            self.file_present: {
                'user': salt.utils.path.get_user(self.file_present),
                'group': salt.utils.path.get_group(self.file_present),
                'mode': '0123'
            }
        }
        self.assertEqual(wanted_ret, salt.utils.path.set_perms(self.file_present,
                                                               mode='0123'))

    ### For symlink.
    def test_set_perms_symlink_no_changes(self):
        wanted_ret = {
            self.link_file_one_present: {
                'user': salt.utils.path.get_user(self.link_file_one_present),
                'group': salt.utils.path.get_group(self.link_file_one_present),
                'mode': salt.utils.path.get_mode(self.link_file_one_present)
            }
        }
        self.assertEqual(wanted_ret, salt.utils.path.set_perms(self.link_file_one_present))

    def test_set_perms_symlink_change_user(self):
        wanted_ret = {
            self.link_file_one_present: {
                'user': salt.utils.path.get_user(self.link_file_one_present),
                'group': salt.utils.path.get_group(self.link_file_one_present),
                'mode': salt.utils.path.get_mode(self.link_file_one_present)
            }
        }
        self.assertEqual(wanted_ret, salt.utils.path.set_perms(self.link_file_one_present,
                                                               user=self.user['name']))

    def test_set_perms_symlink_change_group(self):
        wanted_ret = {
            self.link_file_one_present: {
                'user': salt.utils.path.get_user(self.link_file_one_present),
                'group': salt.utils.path.get_group(self.link_file_one_present),
                'mode': salt.utils.path.get_mode(self.link_file_one_present)
            }
        }
        self.assertEqual(wanted_ret, salt.utils.path.set_perms(self.link_file_one_present,
                                                               group=self.group['name']))

    def test_set_perms_symlink_change_mode(self):
        wanted_ret = {
            self.link_file_one_present: {
                'user': salt.utils.path.get_user(self.link_file_one_present),
                'group': salt.utils.path.get_group(self.link_file_one_present),
                'mode': salt.utils.path.get_mode(self.link_file_one_present)
            }
        }
        self.assertEqual(wanted_ret, salt.utils.path.set_perms(self.link_file_one_present,
                                                               mode='0123'))

    ### For directories.
    def test_set_perms_dir_no_changes_recursive_False(self):
        wanted_ret = {
            self.dir_one_present: {
                'user': salt.utils.path.get_user(self.dir_one_present),
                'group': salt.utils.path.get_group(self.dir_one_present),
                'mode': salt.utils.path.get_mode(self.dir_one_present)
            }
        }
        self.assertEqual(wanted_ret, salt.utils.path.set_perms(self.dir_one_present,
                                                               recursive=False))

    def test_set_perms_dir_change_user_recursive_False(self):
        wanted_ret = {
            self.dir_one_present: {
                'user': self.user['name'],
                'group': salt.utils.path.get_group(self.dir_one_present),
                'mode': salt.utils.path.get_mode(self.dir_one_present)
            }
        }
        self.assertEqual(wanted_ret, salt.utils.path.set_perms(self.dir_one_present, user=self.user['name'],
                                                               recursive=False))

    def test_set_perms_dir_change_group_recursive_False(self):
        wanted_ret = {
            self.dir_one_present: {
                'user': salt.utils.path.get_user(self.dir_one_present),
                'group': self.group['name'],
                'mode': salt.utils.path.get_mode(self.dir_one_present)
            }
        }
        self.assertEqual(wanted_ret, salt.utils.path.set_perms(self.dir_one_present, group=self.group['name'],
                                                               recursive=False))

    def test_set_perms_dir_change_mode_recursive_False(self):
        wanted_ret = {
            self.dir_one_present: {
                'user': salt.utils.path.get_user(self.dir_one_present),
                'group': salt.utils.path.get_group(self.dir_one_present),
                'mode': '0123'
            }
        }
        self.assertEqual(wanted_ret, salt.utils.path.set_perms(self.dir_one_present, mode='0123',
                                                               recursive=False))

    ### For directories recursive.
    def test_set_perms_dir_change_all_recursive_True_mode(self):
        wanted_ret = {
            self.dir_one_present: {
                'user': self.user['name'],
                'group': self.group['name'],
                'mode': '0123'
            },
            self.file_one_present: {
                'user': self.user['name'],
                'group': self.group['name'],
                'mode': '0123'
            }
        }
        self.assertEqual(wanted_ret, salt.utils.path.set_perms(self.dir_one_present,
                                                               user=self.user['name'],
                                                               group=self.group['name'],
                                                               mode='0123'))

# @skipIf(NO_MOCK, NO_MOCK_REASON)
# @destructiveTest
class path_remove_copy_move_TestCase(TestCase):

    def setUp(self):
        self.working_dir = tempfile.TemporaryDirectory().name
        self.file_present = os.path.join(self.working_dir, 'file_present')
        self.dir_one_present = os.path.join(self.working_dir, 'dir_one_present')
        self.file_one_present = os.path.join(self.dir_one_present, 'file_one_present')
        self.link_file_one_present = os.path.join(self.working_dir, 'link_file_one_present')
        self.dir_two_present = os.path.join(self.working_dir, 'dir_two_present')
        self.link_dir_two_present = os.path.join(self.working_dir, 'link_dir_two_present')
        self.file_two_present = os.path.join(self.dir_two_present, 'file_two_present')
        self.dir_tree_present = os.path.join(self.working_dir, 'dir_tree_present')
        self.file_tree_absent = os.path.join(self.dir_tree_present, 'file_tree_absent')
        self.link_file_tree_absent = os.path.join(self.working_dir, 'link_file_tree_absent')
        self.dir_four_absent = os.path.join(self.working_dir, 'dir_four_absent')
        self.link_dir_four_absent = os.path.join(self.working_dir, 'link_dir_four_absent')
        self.dir_five_present = os.path.join(self.working_dir, 'dir_five_present')

        self.other_dir = tempfile.TemporaryDirectory().name
        self.link_other_dir_present = os.path.join(self.working_dir, 'link_other_dir_present')
        self.other_file_present = os.path.join(self.other_dir, 'other_file_present')
        self.link_other_file_present = os.path.join(self.working_dir, 'link_other_file_present')

        salt.utils.path.dir_is_present(self.working_dir)
        salt.utils.path.file_is_present(self.file_present)
        salt.utils.path.dir_is_present(self.dir_one_present)
        salt.utils.path.file_is_present(self.file_one_present)
        salt.utils.path.set_link(self.file_one_present, self.link_file_one_present)
        salt.utils.path.dir_is_present(self.dir_two_present)
        salt.utils.path.set_link(self.dir_two_present, self.link_dir_two_present)
        salt.utils.path.file_is_present(self.file_two_present)
        salt.utils.path.dir_is_present(self.dir_tree_present)
        salt.utils.path.set_link(self.file_tree_absent, self.link_file_tree_absent)
        salt.utils.path.set_link(self.dir_four_absent, self.link_dir_four_absent)
        salt.utils.path.dir_is_present(self.dir_five_present)

        salt.utils.path.dir_is_present(self.other_dir)
        salt.utils.path.set_link(self.other_dir, self.link_other_dir_present)
        salt.utils.path.file_is_present(self.other_file_present)
        salt.utils.path.set_link(self.other_file_present, self.link_other_file_present)

    def tearDown(self):
        salt.utils.path.file_is_absent(self.link_other_file_present)
        salt.utils.path.file_is_absent(self.other_file_present)
        salt.utils.path.file_is_absent(self.link_other_dir_present)
        salt.utils.path.dir_is_absent(self.other_dir)

        salt.utils.path.dir_is_absent(self.dir_four_absent)
        salt.utils.path.dir_is_absent(self.dir_five_present)
        salt.utils.path.file_is_absent(self.file_tree_absent)
        salt.utils.path.file_is_absent(self.link_dir_four_absent)
        salt.utils.path.file_is_absent(self.link_file_tree_absent)
        salt.utils.path.dir_is_absent(self.dir_tree_present)
        salt.utils.path.file_is_absent(self.file_two_present)
        salt.utils.path.file_is_absent(self.link_dir_two_present)
        salt.utils.path.dir_is_absent(self.dir_two_present)
        salt.utils.path.file_is_absent(self.link_file_one_present)
        salt.utils.path.file_is_absent(self.file_one_present)
        salt.utils.path.dir_is_absent(self.dir_one_present)
        salt.utils.path.file_is_absent(self.file_present)
        salt.utils.path.dir_is_absent(self.working_dir)

        del self.link_other_file_present
        del self.other_file_present
        del self.link_other_dir_present
        del self.other_dir

        del self.link_dir_four_absent
        del self.dir_four_absent
        del self.link_file_tree_absent
        del self.file_tree_absent
        del self.dir_tree_present
        del self.file_two_present
        del self.link_dir_two_present
        del self.dir_two_present
        del self.link_file_one_present
        del self.file_one_present
        del self.dir_one_present
        del self.file_present
        del self.working_dir

    #  FUNC: remove
    ##################################################
    def test_dir_remove_file_absent(self):
        self.assertEqual([self.file_tree_absent], salt.utils.path.remove(self.file_tree_absent))
        self.assertFalse(salt.utils.path.exist(self.file_tree_absent))

    def test_dir_remove_file_present(self):
        self.assertEqual([self.file_present], salt.utils.path.remove(self.file_present))
        self.assertFalse(salt.utils.path.exist(self.file_present))

    def test_dir_remove_dir_absent(self):
        self.assertEqual([self.dir_four_absent], salt.utils.path.remove(self.dir_four_absent))
        self.assertFalse(salt.utils.path.exist(self.dir_four_absent))

    def test_dir_remove_dir_present(self):
        self.assertEqual([self.dir_tree_present], salt.utils.path.remove(self.dir_tree_present))
        self.assertFalse(salt.utils.path.exist(self.dir_tree_present))

    def test_dir_remove_symlink_file_absent(self):
        self.assertEqual([self.link_file_tree_absent], salt.utils.path.remove(self.link_file_tree_absent))
        self.assertFalse(salt.utils.path.exist(self.link_file_tree_absent))

    def test_dir_remove_symlink_file_present(self):
        self.assertEqual([self.link_file_one_present], salt.utils.path.remove(self.link_file_one_present))
        self.assertFalse(salt.utils.path.exist(self.link_file_one_present))
        self.assertTrue(salt.utils.path.exist(self.file_one_present))

    def test_dir_remove_symlink_dir_absent(self):
        self.assertEqual([self.link_dir_four_absent], salt.utils.path.remove(self.link_dir_four_absent))
        self.assertFalse(salt.utils.path.exist(self.link_dir_four_absent))

    def test_dir_remove_symlink_dir_present(self):
        self.assertEqual([self.link_dir_two_present], salt.utils.path.remove(self.link_dir_two_present))
        self.assertFalse(salt.utils.path.exist(self.link_dir_two_present))
        self.assertTrue(salt.utils.path.exist(self.dir_two_present))

    def test_dir_remove_dir_not_empty(self):
        self.assertEqual([], salt.utils.path.remove(self.dir_one_present))
        self.assertTrue(salt.utils.path.exist(self.dir_one_present))
        self.assertTrue(salt.utils.path.exist(self.file_one_present))

    def test_dir_remove_dir_not_empty_recursive_True(self):
        wanted_ret = sorted([self.working_dir,
                             self.file_present,
                             self.dir_one_present,
                             self.file_one_present,
                             self.dir_two_present,
                             self.file_two_present,
                             self.dir_tree_present,
                             self.dir_five_present,
                             self.link_dir_four_absent,
                             self.link_dir_two_present,
                             self.link_file_one_present,
                             self.link_file_tree_absent,
                             self.link_other_dir_present,
                             self.link_other_file_present])
        self.assertEqual(wanted_ret, salt.utils.path.remove(self.working_dir, recursive=True))

    def test_dir_remove_dir_not_empty_follow_symlinks_True(self):
        self.assertEqual([], salt.utils.path.remove(self.working_dir, follow_symlinks=True))

    def test_dir_remove_dir_not_empty_recursive_True_follow_symlinks_True(self):
        wanted_ret = sorted([self.working_dir,
                             self.file_present,
                             self.dir_one_present,
                             self.file_one_present,
                             self.dir_two_present,
                             self.file_two_present,
                             self.dir_tree_present,
                             self.dir_four_absent,
                             self.dir_five_present,
                             self.file_tree_absent,
                             self.other_dir,
                             self.other_file_present,
                             self.link_dir_four_absent,
                             self.link_dir_two_present,
                             self.link_file_one_present,
                             self.link_file_tree_absent,
                             self.link_other_dir_present,
                             self.link_other_file_present])
        actual_ret = salt.utils.path.remove(self.working_dir, recursive=True, follow_symlinks=True)

        self.assertFalse(salt.utils.path.exist(self.other_dir))
        self.assertFalse(salt.utils.path.exist(self.working_dir))
        self.assertEqual(wanted_ret, actual_ret)

    #  FUNC: move
    ##################################################
    def test_move_file_absent(self):
        wanted_ret = {'added': [], 'removed': []}
        self.assertEqual(wanted_ret, salt.utils.path.move(self.file_tree_absent, self.file_tree_absent))
        self.assertFalse(salt.utils.path.exist(self.file_tree_absent))

    def test_move_file_present(self):
        wanted_ret = {'added': [self.file_tree_absent], 'removed': [self.file_present]}
        self.assertEqual(wanted_ret, salt.utils.path.move(self.file_present, self.file_tree_absent))
        self.assertTrue(salt.utils.path.exist(self.file_tree_absent))
        self.assertFalse(salt.utils.path.exist(self.file_present))

    def test_move_dir_absent(self):
        wanted_ret = {'added': [], 'removed': []}
        self.assertEqual(wanted_ret, salt.utils.path.move(self.dir_four_absent, self.dir_four_absent))
        self.assertFalse(salt.utils.path.exist(self.dir_four_absent))

    def test_move_dir_present(self):
        wanted_ret = {'added': [self.dir_four_absent], 'removed': [self.dir_five_present]}
        self.assertEqual(wanted_ret, salt.utils.path.move(self.dir_five_present, self.dir_four_absent))
        self.assertFalse(salt.utils.path.exist(self.dir_five_present))
        self.assertTrue(salt.utils.path.exist(self.dir_four_absent))

    def test_move_symlink_file_absent(self):
        wanted_ret = {'added': [], 'removed': [self.link_file_tree_absent]}
        self.assertEqual(wanted_ret, salt.utils.path.move(self.link_file_tree_absent, self.link_file_tree_absent))
        self.assertFalse(salt.utils.path.exist(self.link_file_tree_absent))

    def test_move_symlink_file_present(self):
        wanted_ret = {'added': [self.link_file_tree_absent], 'removed': [self.link_file_one_present]}
        self.assertEqual(wanted_ret, salt.utils.path.move(self.link_file_one_present, self.link_file_tree_absent))
        self.assertTrue(salt.utils.path.exist(self.link_file_tree_absent))
        self.assertFalse(salt.utils.path.exist(self.link_file_one_present))

    def test_move_dir_not_empty(self):
        wanted_ret = {
            'added': [
                self.dir_four_absent,
                salt.utils.path.join(self.dir_four_absent, salt.utils.path.get_basename(self.file_one_present))
            ],
            'removed': [
                self.dir_one_present,
                self.file_one_present
            ]
        }
        self.assertEqual(wanted_ret, salt.utils.path.move(self.dir_one_present, self.dir_four_absent))
        self.assertFalse(salt.utils.path.exist(self.dir_one_present))
        self.assertTrue(salt.utils.path.exist(self.dir_four_absent))

    #  FUNC: copy
    ##################################################
    def test_copy_file_absent(self):
        wanted_ret = {'added': [], 'removed': []}
        self.assertEqual(wanted_ret, salt.utils.path.copy(self.file_tree_absent, self.file_tree_absent))
        self.assertFalse(salt.utils.path.exist(self.file_tree_absent))

    def test_copy_file_present(self):
        wanted_ret = {'added': [self.file_tree_absent], 'removed': []}
        self.assertEqual(wanted_ret, salt.utils.path.copy(self.file_present, self.file_tree_absent))
        self.assertTrue(salt.utils.path.exist(self.file_tree_absent))
        self.assertTrue(salt.utils.path.exist(self.file_present))

    def test_copy_dir_absent(self):
        wanted_ret = {'added': [], 'removed': []}
        self.assertEqual(wanted_ret, salt.utils.path.copy(self.dir_four_absent, self.dir_four_absent))
        self.assertFalse(salt.utils.path.exist(self.dir_four_absent))

    def test_copy_dir_present(self):
        wanted_ret = {'added': [self.dir_four_absent], 'removed': []}
        self.assertEqual(wanted_ret, salt.utils.path.copy(self.dir_five_present, self.dir_four_absent))
        self.assertTrue(salt.utils.path.exist(self.dir_five_present))
        self.assertTrue(salt.utils.path.exist(self.dir_four_absent))

    def test_copy_symlink_file_absent(self):
        wanted_ret = {'added': [], 'removed': []}
        self.assertEqual(wanted_ret, salt.utils.path.copy(self.link_file_tree_absent, self.link_file_tree_absent))
        self.assertFalse(salt.utils.path.exist(self.link_file_tree_absent))

    def test_copy_symlink_file_present(self):
        wanted_ret = {'added': [self.link_file_tree_absent], 'removed': []}
        self.assertEqual(wanted_ret, salt.utils.path.copy(self.link_file_one_present, self.link_file_tree_absent))
        self.assertTrue(salt.utils.path.exist(self.link_file_tree_absent))
        self.assertTrue(salt.utils.path.exist(self.link_file_one_present))

    def test_copy_dir_not_empty(self):
        wanted_ret = {
            'added': [
                self.dir_four_absent,
                salt.utils.path.join(self.dir_four_absent, salt.utils.path.get_basename(self.file_one_present))
            ],
            'removed': [

            ]
        }
        self.assertEqual(wanted_ret, salt.utils.path.copy(self.dir_one_present, self.dir_four_absent))
        self.assertTrue(salt.utils.path.exist(self.dir_one_present))
        self.assertTrue(salt.utils.path.exist(self.dir_four_absent))

    def test_copy_dir_not_empty_recursive_True(self):
        wanted_ret = {
            'added': [
                self.dir_four_absent,
                salt.utils.path.join(self.dir_four_absent, salt.utils.path.get_basename(self.file_one_present))
            ],
            'removed': [

            ]
        }
        self.assertEqual(wanted_ret, salt.utils.path.copy(self.dir_one_present, self.dir_four_absent, recursive=True))
        self.assertTrue(salt.utils.path.exist(self.dir_one_present))
        self.assertTrue(salt.utils.path.exist(self.dir_four_absent))

    #  FUNC: dir_is_absent
    ##################################################
    def test_dir_is_absent_empty(self):
        self.assertTrue(salt.utils.path.dir_is_absent(self.dir_tree_present))
        self.assertFalse(salt.utils.path.exist(self.dir_tree_present))

    def test_dir_is_absent_not_empty(self):
        self.assertFalse(salt.utils.path.dir_is_absent(self.dir_two_present))
        self.assertTrue(salt.utils.path.exist(self.dir_two_present))

    def test_dir_is_absent_dir_absent(self):
        self.assertTrue(salt.utils.path.dir_is_absent(self.dir_four_absent))
        self.assertFalse(salt.utils.path.exist(self.dir_four_absent))

    def test_dir_is_absent_file(self):
        self.assertFalse(salt.utils.path.dir_is_absent(self.file_present))
        self.assertTrue(salt.utils.path.exist(self.dir_two_present))

    def test_dir_is_absent_symlink_to_file(self):
        self.assertFalse(salt.utils.path.dir_is_absent(self.link_file_one_present))
        self.assertTrue(salt.utils.path.exist(self.link_file_one_present))
        self.assertTrue(salt.utils.path.exist(self.file_one_present))

    def test_dir_is_absent_symlink_to_dir(self):
        self.assertFalse(salt.utils.path.dir_is_absent(self.link_dir_two_present))
        self.assertTrue(salt.utils.path.exist(self.link_dir_two_present))
        self.assertTrue(salt.utils.path.exist(self.dir_two_present))

    def test_dir_is_absent_symlink_broken(self):
        self.assertTrue(salt.utils.path.dir_is_absent(self.link_file_tree_absent))
        self.assertFalse(salt.utils.path.exist(self.link_file_tree_absent))
        self.assertFalse(salt.utils.path.exist(self.file_tree_absent))

    #  FUNC: file_is_absent
    ##################################################
    def test_file_is_absent_dir(self):
        self.assertFalse(salt.utils.path.file_is_absent(self.dir_tree_present))
        self.assertTrue(salt.utils.path.exist(self.dir_tree_present))

    def test_file_is_absent_file(self):
        self.assertTrue(salt.utils.path.file_is_absent(self.file_present))
        self.assertFalse(salt.utils.path.exist(self.file_present))

    def test_file_is_absent_file_absent(self):
        self.assertTrue(salt.utils.path.file_is_absent(self.file_tree_absent))
        self.assertFalse(salt.utils.path.exist(self.file_tree_absent))

    def test_file_is_absent_symlink_to_file(self):
        self.assertTrue(salt.utils.path.file_is_absent(self.link_file_one_present))
        self.assertFalse(salt.utils.path.exist(self.link_file_one_present))
        self.assertTrue(salt.utils.path.exist(self.file_one_present))

    def test_file_is_absent_symlink_to_dir(self):
        self.assertTrue(salt.utils.path.file_is_absent(self.link_dir_two_present))
        self.assertFalse(salt.utils.path.exist(self.link_dir_two_present))
        self.assertTrue(salt.utils.path.exist(self.dir_two_present))

    def test_file_is_absent_symlink_broken(self):
        self.assertTrue(salt.utils.path.file_is_absent(self.link_file_tree_absent))
        self.assertFalse(salt.utils.path.exist(self.link_file_tree_absent))
        self.assertFalse(salt.utils.path.exist(self.file_tree_absent))

    #  FUNC: dir_to_list
    ##################################################
    def test_dir_to_list_not_empty(self):
        self.assertEqual([self.file_one_present], salt.utils.path.dir_to_list(self.dir_one_present))

    def test_dir_to_list_link_to_file_follow_symlinks_True(self):
        self.assertEqual([], salt.utils.path.dir_to_list(self.link_file_one_present, follow_symlinks=True))

    def test_dir_to_list_link_to_dir_follow_symlinks_True(self):
        self.assertEqual([self.file_two_present], salt.utils.path.dir_to_list(self.link_dir_two_present, follow_symlinks=True))

    def test_dir_to_list_file_and_dir_and_symlink(self):
        wanted_ret = sorted([self.file_present,
                             self.dir_one_present,
                             self.dir_two_present,
                             self.dir_tree_present,
                             self.dir_five_present,
                             self.link_file_one_present,
                             self.link_dir_two_present,
                             self.link_file_tree_absent,
                             self.link_dir_four_absent,
                             self.link_other_dir_present,
                             self.link_other_file_present])
        self.assertEqual(wanted_ret, salt.utils.path.dir_to_list(self.working_dir))

    def test_dir_to_list_file_and_dir_and_symlink_recurse_True(self):
        wanted_ret = sorted([self.file_present,
                             self.dir_one_present,
                             self.file_one_present,
                             self.dir_two_present,
                             self.file_two_present,
                             self.dir_tree_present,
                             self.dir_five_present,
                             self.link_file_one_present,
                             self.link_dir_two_present,
                             self.link_file_tree_absent,
                             self.link_dir_four_absent,
                             self.link_other_dir_present,
                             self.link_other_file_present])
        self.assertEqual(wanted_ret, salt.utils.path.dir_to_list(self.working_dir, recursive=True))

    def test_dir_to_list_file_and_dir_and_symlink_follow_symlinks_True(self):
        wanted_ret = sorted([self.file_present,
                             self.dir_one_present,
                             self.file_one_present,
                             self.dir_two_present,
                             self.file_two_present,
                             self.dir_tree_present,
                             self.file_tree_absent,
                             self.dir_four_absent,
                             self.dir_five_present,
                             self.other_dir,
                             self.other_file_present,
                             self.link_file_one_present,
                             self.link_dir_two_present,
                             self.link_file_tree_absent,
                             self.link_dir_four_absent,
                             self.link_other_dir_present,
                             self.link_other_file_present])
        self.assertEqual(wanted_ret, salt.utils.path.dir_to_list(self.working_dir, follow_symlinks=True))

    def test_dir_to_list_empty(self):
        self.assertEqual([], salt.utils.path.dir_to_list(self.dir_tree_present))

    def test_dir_to_list_file(self):
        self.assertEqual([], salt.utils.path.dir_to_list(self.file_present))

    def test_dir_to_list_symlink_to_file(self):
        self.assertEqual([], salt.utils.path.dir_to_list(self.link_file_one_present))

    def test_dir_to_list_symlink_to_file_follow_symlinks_True(self):
        self.assertEqual([], salt.utils.path.dir_to_list(self.link_file_one_present, follow_symlinks=True))

    def test_dir_to_list_symlink_to_dir(self):
        self.assertEqual([], salt.utils.path.dir_to_list(self.link_dir_two_present))

    def test_dir_to_list_symlink_to_dir_follow_symlinks_True(self):
        self.assertEqual([self.file_two_present], salt.utils.path.dir_to_list(self.link_dir_two_present, follow_symlinks=True))

    def test_dir_to_list_symlink_broken(self):
        self.assertEqual([], salt.utils.path.dir_to_list(self.link_file_tree_absent))

    def test_dir_to_list_symlink_broken_follow_symlinks_True(self):
        self.assertEqual([], salt.utils.path.dir_to_list(self.link_file_tree_absent, follow_symlinks=True))

    #  FUNC: is_dir
    ##################################################
    def test_is_dir_not_empty(self):
        self.assertTrue(salt.utils.path.is_dir(self.dir_two_present))

    def test_is_dir_empty(self):
        self.assertTrue(salt.utils.path.is_dir(self.dir_tree_present))

    def test_is_dir_file(self):
        self.assertFalse(salt.utils.path.is_dir(self.file_present))

    def test_is_dir_symlink_to_file(self):
        self.assertFalse(salt.utils.path.is_dir(self.link_file_one_present))

    def test_is_dir_symlink_to_dir(self):
        self.assertTrue(salt.utils.path.is_dir(self.link_dir_two_present))

    def test_is_dir_symlink_broken(self):
        self.assertFalse(salt.utils.path.is_dir(self.link_file_tree_absent))

    #  FUNC: is_file
    ##################################################
    def test_is_file(self):
        self.assertTrue(salt.utils.path.is_file(self.file_present))

    def test_is_file_dir(self):
        self.assertFalse(salt.utils.path.is_file(self.dir_one_present))

    def test_is_file_symlink_to_file(self):
        self.assertTrue(salt.utils.path.is_file(self.link_file_one_present))

    def test_is_file_symlink_to_dir(self):
        self.assertFalse(salt.utils.path.is_file(self.link_dir_two_present))

    def test_is_file_symlink_broken(self):
        self.assertFalse(salt.utils.path.is_file(self.link_file_tree_absent))

    #  FUNC: is_symlink
    ##################################################
    def test_is_symlink_file(self):
        self.assertFalse(salt.utils.path.is_symlink(self.file_present))

    def test_is_symlink_dir(self):
        self.assertFalse(salt.utils.path.is_symlink(self.dir_one_present))

    def test_is_symlink_symlink_to_file(self):
        self.assertTrue(salt.utils.path.is_symlink(self.link_file_one_present))

    def test_is_symlink_symlink_to_dir(self):
        self.assertTrue(salt.utils.path.is_symlink(self.link_dir_two_present))

    def test_is_symlink_symlink_broken(self):
        self.assertTrue(salt.utils.path.is_symlink(self.link_file_tree_absent))

    #  FUNC: get_absolute
    ##################################################
    def test_get_absolute_file_not_exist(self):
        self.assertEqual('',
                         salt.utils.path.get_absolute('none'))

    def test_get_absolute_file(self):
        self.assertEqual(self.file_present,
                         salt.utils.path.get_absolute(self.file_present))

    def test_get_absolute_file_with_relative(self):
        self.assertEqual(self.file_one_present + '/../file_one_present',
                         salt.utils.path.get_absolute(self.file_one_present + '/../file_one_present'))

    def test_get_absolute_file_with_relative_resolve_True(self):
        self.assertEqual(self.file_one_present,
                         salt.utils.path.get_absolute(self.file_one_present + '/../file_one_present', resolve=True))

    def test_get_absolute_file_with_relative_follow_symlinks_True(self):
        self.assertEqual(self.file_one_present + '/../file_one_present',
                         salt.utils.path.get_absolute(self.file_one_present + '/../file_one_present', follow_symlinks=True))

    def test_get_absolute_dir(self):
        self.assertEqual(self.dir_one_present, salt.utils.path.get_absolute(self.dir_one_present))

    def test_get_absolute_dir_with_relative(self):
        self.assertEqual(self.dir_one_present + '/../dir_one_present',
                         salt.utils.path.get_absolute(self.dir_one_present + '/../dir_one_present'))

    def test_get_absolute_dir_with_relative_resolve_True(self):
        self.assertEqual(self.dir_one_present,
                         salt.utils.path.get_absolute(self.dir_one_present + '/../dir_one_present', resolve=True))

    def test_get_absolute_dir_with_relative_follow_symlinks_True(self):
        self.assertEqual(self.dir_one_present + '/../dir_one_present',
                         salt.utils.path.get_absolute(self.dir_one_present + '/../dir_one_present', follow_symlinks=True))

    def test_get_absolute_symlink_to_file(self):
        self.assertEqual(self.link_file_one_present, salt.utils.path.get_absolute(self.link_file_one_present))

    def test_get_absolute_symlink_to_file_resolve_True(self):
        self.assertEqual(self.link_file_one_present,
                         salt.utils.path.get_absolute(self.link_file_one_present, resolve=True))

    def test_get_absolute_symlink_to_file_follow_symlinks_True(self):
        self.assertEqual(self.file_one_present,
                         salt.utils.path.get_absolute(self.link_file_one_present, follow_symlinks=True))

    def test_get_absolute_symlink_to_dir(self):
        self.assertEqual(self.link_dir_two_present, salt.utils.path.get_absolute(self.link_dir_two_present))

    def test_get_absolute_symlink_to_dir_resolve_True(self):
        self.assertEqual(self.link_dir_two_present,
                         salt.utils.path.get_absolute(self.link_dir_two_present, resolve=True))

    def test_get_absolute_symlink_to_dir_follow_symlinks_True(self):
        self.assertEqual(self.dir_two_present,
                         salt.utils.path.get_absolute(self.link_dir_two_present, follow_symlinks=True))

    def test_get_absolute_symlink_to_dir_resolve_True_follow_symlinks_True(self):
        self.assertEqual(self.dir_two_present,
                         salt.utils.path.get_absolute(self.link_dir_two_present, resolve=True, follow_symlinks=True))

    def test_get_absolute_symlink_broken(self):
        self.assertEqual(self.link_file_tree_absent, salt.utils.path.get_absolute(self.link_file_tree_absent))

    def test_get_absolute_symlink_broken_resolve_True(self):
        self.assertEqual(self.link_file_tree_absent,
                         salt.utils.path.get_absolute(self.link_file_tree_absent, resolve=True))

    def test_get_absolute_symlink_broken_follow_symlinks_True(self):
        self.assertEqual(self.file_tree_absent,
                         salt.utils.path.get_absolute(self.link_file_tree_absent, follow_symlinks=True))
