# -*- coding: utf-8 -*-
'''
mac_utils tests
'''

# Import python libs
from __future__ import absolute_import, unicode_literals
import plistlib
import xml.parsers.expat
import os

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    call,
    MagicMock,
    mock_open,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)
from tests.support.mixins import LoaderModuleMockMixin

# Import Salt libs
import salt.utils.mac_utils as mac_utils
import salt.utils.platform
from salt.exceptions import SaltInvocationError, CommandExecutionError

# Import 3rd-party libs
from salt.ext.six.moves import range
from salt.ext import six


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not salt.utils.platform.is_darwin(), 'These tests run only on mac')
class MacUtilsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    test mac_utils salt utility
    '''
    def setup_loader_modules(self):
        return {mac_utils: {}}

    def test_execute_return_success_not_supported(self):
        '''
        test execute_return_success function
        command not supported
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'not supported',
                                           'stderr': 'error'})
        with patch.object(mac_utils, '_run_all', mock_cmd):
            self.assertRaises(CommandExecutionError,
                              mac_utils.execute_return_success,
                              'dir c:\\')

    def test_execute_return_success_command_failed(self):
        '''
        test execute_return_success function
        command failed
        '''
        mock_cmd = MagicMock(return_value={'retcode': 1,
                                           'stdout': 'spongebob',
                                           'stderr': 'error'})
        with patch.object(mac_utils, '_run_all', mock_cmd):
            self.assertRaises(CommandExecutionError,
                              mac_utils.execute_return_success,
                              'dir c:\\')

    def test_execute_return_success_command_succeeded(self):
        '''
        test execute_return_success function
        command succeeded
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob'})
        with patch.object(mac_utils, '_run_all', mock_cmd):
            ret = mac_utils.execute_return_success('dir c:\\')
            self.assertEqual(ret, True)

    def test_execute_return_result_command_failed(self):
        '''
        test execute_return_result function
        command failed
        '''
        mock_cmd = MagicMock(return_value={'retcode': 1,
                                           'stdout': 'spongebob',
                                           'stderr': 'squarepants'})
        with patch.object(mac_utils, '_run_all', mock_cmd):
            self.assertRaises(CommandExecutionError,
                              mac_utils.execute_return_result,
                              'dir c:\\')

    def test_execute_return_result_command_succeeded(self):
        '''
        test execute_return_result function
        command succeeded
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'spongebob'})
        with patch.object(mac_utils, '_run_all', mock_cmd):
            ret = mac_utils.execute_return_result('dir c:\\')
            self.assertEqual(ret, 'spongebob')

    def test_parse_return_space(self):
        '''
        test parse_return function
        space after colon
        '''
        self.assertEqual(mac_utils.parse_return('spongebob: squarepants'),
                         'squarepants')

    def test_parse_return_new_line(self):
        '''
        test parse_return function
        new line after colon
        '''
        self.assertEqual(mac_utils.parse_return('spongebob:\nsquarepants'),
                         'squarepants')

    def test_parse_return_no_delimiter(self):
        '''
        test parse_return function
        no delimiter
        '''
        self.assertEqual(mac_utils.parse_return('squarepants'),
                         'squarepants')

    def test_validate_enabled_on(self):
        '''
        test validate_enabled function
        test on
        '''
        self.assertEqual(mac_utils.validate_enabled('On'),
                         'on')

    def test_validate_enabled_off(self):
        '''
        test validate_enabled function
        test off
        '''
        self.assertEqual(mac_utils.validate_enabled('Off'),
                         'off')

    def test_validate_enabled_bad_string(self):
        '''
        test validate_enabled function
        test bad string
        '''
        self.assertRaises(SaltInvocationError,
                          mac_utils.validate_enabled,
                          'bad string')

    def test_validate_enabled_non_zero(self):
        '''
        test validate_enabled function
        test non zero
        '''
        for x in range(1, 179, 3):
            self.assertEqual(mac_utils.validate_enabled(x),
                             'on')

    def test_validate_enabled_0(self):
        '''
        test validate_enabled function
        test 0
        '''
        self.assertEqual(mac_utils.validate_enabled(0),
                         'off')

    def test_validate_enabled_true(self):
        '''
        test validate_enabled function
        test True
        '''
        self.assertEqual(mac_utils.validate_enabled(True),
                         'on')

    def test_validate_enabled_false(self):
        '''
        test validate_enabled function
        test False
        '''
        self.assertEqual(mac_utils.validate_enabled(False),
                         'off')

    def test_launchctl(self):
        '''
        test launchctl function
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'success',
                                           'stderr': 'none'})
        with patch('salt.utils.mac_utils.__salt__', {'cmd.run_all': mock_cmd}):
            ret = mac_utils.launchctl('enable', 'org.salt.minion')
            self.assertEqual(ret, True)

    def test_launchctl_return_stdout(self):
        '''
        test launchctl function and return stdout
        '''
        mock_cmd = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'success',
                                           'stderr': 'none'})
        with patch('salt.utils.mac_utils.__salt__', {'cmd.run_all': mock_cmd}):
            ret = mac_utils.launchctl('enable',
                                      'org.salt.minion',
                                      return_stdout=True)
            self.assertEqual(ret, 'success')

    def test_launchctl_error(self):
        '''
        test launchctl function returning an error
        '''
        mock_cmd = MagicMock(return_value={'retcode': 1,
                                           'stdout': 'failure',
                                           'stderr': 'test failure'})
        error = 'Failed to enable service:\n' \
                'stdout: failure\n' \
                'stderr: test failure\n' \
                'retcode: 1'
        with patch('salt.utils.mac_utils.__salt__', {'cmd.run_all': mock_cmd}):
            try:
                mac_utils.launchctl('enable', 'org.salt.minion')
            except CommandExecutionError as exc:
                self.assertEqual(exc.message, error)

    @patch('salt.utils.path.os_walk')
    @patch('os.path.exists')
    def test_available_services_result(self, mock_exists, mock_os_walk):
        '''
        test available_services results are properly formed dicts.
        '''
        results = {'/Library/LaunchAgents': ['com.apple.lla1.plist']}
        mock_os_walk.side_effect = _get_walk_side_effects(results)
        mock_exists.return_value = True

        plists = [{'Label': 'com.apple.lla1'}]
        ret = _run_available_services(plists)

        file_path = os.sep + os.path.join('Library', 'LaunchAgents', 'com.apple.lla1.plist')
        if salt.utils.platform.is_windows():
            file_path = 'c:' + file_path

        expected = {
            'com.apple.lla1': {
                'file_name': 'com.apple.lla1.plist',
                'file_path': file_path,
                'plist': plists[0]}}
        self.assertEqual(ret, expected)

    @patch('salt.utils.path.os_walk')
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('os.path.isdir')
    def test_available_services_dirs(self,
                                     mock_isdir,
                                     mock_listdir,
                                     mock_exists,
                                     mock_os_walk):
        '''
        test available_services checks all of the expected dirs.
        '''
        results = {
            '/Library/LaunchAgents': ['com.apple.lla1.plist'],
            '/Library/LaunchDaemons': ['com.apple.lld1.plist'],
            '/System/Library/LaunchAgents': ['com.apple.slla1.plist'],
            '/System/Library/LaunchDaemons': ['com.apple.slld1.plist'],
            '/Users/saltymcsaltface/Library/LaunchAgents': [
                'com.apple.uslla1.plist']}

        mock_os_walk.side_effect = _get_walk_side_effects(results)
        mock_listdir.return_value = ['saltymcsaltface']
        mock_isdir.return_value = True
        mock_exists.return_value = True

        plists = [
            {'Label': 'com.apple.lla1'},
            {'Label': 'com.apple.lld1'},
            {'Label': 'com.apple.slla1'},
            {'Label': 'com.apple.slld1'},
            {'Label': 'com.apple.uslla1'}]
        ret = _run_available_services(plists)

        self.assertEqual(len(ret), 5)

    @patch('salt.utils.path.os_walk')
    @patch('os.path.exists')
    @patch('plistlib.readPlist' if six.PY2 else 'plistlib.load')
    def test_available_services_broken_symlink(self, mock_read_plist, mock_exists, mock_os_walk):
        '''
        test available_services when it encounters a broken symlink.
        '''
        results = {'/Library/LaunchAgents': ['com.apple.lla1.plist', 'com.apple.lla2.plist']}
        mock_os_walk.side_effect = _get_walk_side_effects(results)
        mock_exists.side_effect = [True, False]

        plists = [{'Label': 'com.apple.lla1'}]
        ret = _run_available_services(plists)

        file_path = os.sep + os.path.join('Library', 'LaunchAgents', 'com.apple.lla1.plist')
        if salt.utils.platform.is_windows():
            file_path = 'c:' + file_path

        expected = {
            'com.apple.lla1': {
                'file_name': 'com.apple.lla1.plist',
                'file_path': file_path,
                'plist': plists[0]}}
        self.assertEqual(ret, expected)

    @patch('salt.utils.path.os_walk')
    @patch('os.path.exists')
    @patch('plistlib.readPlist')
    @patch('salt.utils.mac_utils.__salt__')
    @patch('plistlib.readPlistFromString', create=True)
    def test_available_services_binary_plist(self,
                                             mock_read_plist_from_string,
                                             mock_run,
                                             mock_read_plist,
                                             mock_exists,
                                             mock_os_walk):
        '''
        test available_services handles binary plist files.
        '''
        results = {'/Library/LaunchAgents': ['com.apple.lla1.plist']}
        mock_os_walk.side_effect = _get_walk_side_effects(results)
        mock_exists.return_value = True

        plists = [{'Label': 'com.apple.lla1'}]

        file_path = os.sep + os.path.join('Library', 'LaunchAgents', 'com.apple.lla1.plist')
        if salt.utils.platform.is_windows():
            file_path = 'c:' + file_path

        if six.PY2:
            attrs = {'cmd.run': MagicMock()}

            def getitem(name):
                return attrs[name]

            mock_run.__getitem__.side_effect = getitem
            mock_run.configure_mock(**attrs)
            cmd = '/usr/bin/plutil -convert xml1 -o - -- "{}"'.format(file_path)
            calls = [call.cmd.run(cmd)]

            mock_read_plist.side_effect = xml.parsers.expat.ExpatError
            mock_read_plist_from_string.side_effect = plists
            ret = mac_utils._available_services()
        else:
            # Py3 plistlib knows how to handle binary plists without
            # any extra work, so this test doesn't really do anything
            # new.
            ret = _run_available_services(plists)

        expected = {
            'com.apple.lla1': {
                'file_name': 'com.apple.lla1.plist',
                'file_path': file_path,
                'plist': plists[0]}}
        self.assertEqual(ret, expected)

        if six.PY2:
            mock_run.assert_has_calls(calls, any_order=True)

    @patch('salt.utils.path.os_walk')
    @patch('os.path.exists')
    def test_available_services_invalid_file(self, mock_exists, mock_os_walk):
        '''
        test available_services excludes invalid files.

        The py3 plistlib raises an InvalidFileException when a plist
        file cannot be parsed. This test only asserts things for py3.
        '''
        if six.PY3:
            results = {'/Library/LaunchAgents': ['com.apple.lla1.plist']}
            mock_os_walk.side_effect = _get_walk_side_effects(results)
            mock_exists.return_value = True

            plists = [{'Label': 'com.apple.lla1'}]

            mock_load = MagicMock()
            mock_load.side_effect = plistlib.InvalidFileException
            with patch('salt.utils.files.fopen', mock_open()):
                with patch('plistlib.load', mock_load):
                    ret = mac_utils._available_services()

            self.assertEqual(len(ret), 0)

    @patch('salt.utils.mac_utils.__salt__')
    @patch('plistlib.readPlist')
    @patch('salt.utils.path.os_walk')
    @patch('os.path.exists')
    def test_available_services_expat_error(self,
                                            mock_exists,
                                            mock_os_walk,
                                            mock_read_plist,
                                            mock_run):
        '''
        test available_services excludes files with expat errors.

        Poorly formed XML will raise an ExpatError on py2. It will
        also be raised by some almost-correct XML on py3.
        '''
        results = {'/Library/LaunchAgents': ['com.apple.lla1.plist']}
        mock_os_walk.side_effect = _get_walk_side_effects(results)
        mock_exists.return_value = True

        file_path = os.sep + os.path.join('Library', 'LaunchAgents', 'com.apple.lla1.plist')
        if salt.utils.platform.is_windows():
            file_path = 'c:' + file_path

        if six.PY3:
            mock_load = MagicMock()
            mock_load.side_effect = xml.parsers.expat.ExpatError
            with patch('salt.utils.files.fopen', mock_open()):
                with patch('plistlib.load', mock_load):
                    ret = mac_utils._available_services()
        else:
            attrs = {'cmd.run': MagicMock()}

            def getitem(name):
                return attrs[name]

            mock_run.__getitem__.side_effect = getitem
            mock_run.configure_mock(**attrs)
            cmd = '/usr/bin/plutil -convert xml1 -o - -- "{}"'.format(file_path)
            calls = [call.cmd.run(cmd)]

            mock_raise_expat_error = MagicMock(
                side_effect=xml.parsers.expat.ExpatError)

            with patch('plistlib.readPlist', mock_raise_expat_error):
                with patch('plistlib.readPlistFromString', mock_raise_expat_error):
                    ret = mac_utils._available_services()

            mock_run.assert_has_calls(calls, any_order=True)

        self.assertEqual(len(ret), 0)


def _get_walk_side_effects(results):
    '''
    Data generation helper function for service tests.
    '''
    def walk_side_effect(*args, **kwargs):
        return [(args[0], [], results.get(args[0], []))]
    return walk_side_effect


def _run_available_services(plists):
    if six.PY2:
        mock_read_plist = MagicMock()
        mock_read_plist.side_effect = plists
        with patch('plistlib.readPlist', mock_read_plist):
            ret = mac_utils._available_services()
    else:
        mock_load = MagicMock()
        mock_load.side_effect = plists
        with patch('salt.utils.files.fopen', mock_open()):
            with patch('plistlib.load', mock_load):
                ret = mac_utils._available_services()
    return ret
