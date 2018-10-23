# -*- coding: utf-8 -*-
'''
mac_utils tests
'''

# Import python libs
from __future__ import absolute_import, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON, call, mock_open
from tests.support.mixins import LoaderModuleMockMixin

# Import Salt libs
import salt.utils.mac_utils as mac_utils
from salt.exceptions import SaltInvocationError, CommandExecutionError

# Import 3rd-party libs
from salt.ext.six.moves import range
from salt.ext import six


@skipIf(NO_MOCK, NO_MOCK_REASON)
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
    @patch('plistlib.readPlist' if six.PY2 else 'plistlib.load')
    def test_available_services(self, mock_read_plist, mock_exists, mock_os_walk):
        '''
        test available_services
        '''
        def walk_side_effect(*args, **kwargs):
            path = args[0]
            results = {
                '/Library/LaunchAgents': ['com.apple.lla1.plist', 'com.apple.lla2.plist'],
                '/Library/LaunchDaemons': ['com.apple.lld1.plist', 'com.apple.lld2.plist'],
                '/System/Library/LaunchAgents': ['com.apple.slla1.plist', 'com.apple.slla2.plist'],
                '/System/Library/LaunchDaemons': ['com.apple.slld1.plist', 'com.apple.slld2.plist']}
            files = results.get(path, [])
            return [(path, [], files)]

        mock_os_walk.side_effect = walk_side_effect
        mock_read_plist.side_effect = [
            MagicMock(Label='com.apple.lla1'),
            MagicMock(Label='com.apple.lla2'),
            MagicMock(Label='com.apple.lld1'),
            MagicMock(Label='com.apple.lld2'),
            MagicMock(Label='com.apple.slla1'),
            MagicMock(Label='com.apple.slla2'),
            MagicMock(Label='com.apple.slld1'),
            MagicMock(Label='com.apple.slld2'),
        ]

        mock_exists.return_value = True

        if six.PY3:
            # Py3's plistlib.load does not handle opening and closing a
            # file, unlike py2's plistlib.readPlist. Therefore, we have
            # to patch open for py3 since we're using it in addition
            # to the plistlib.load call.
            with patch('salt.utils.files.fopen', mock_open()):
                ret = mac_utils._available_services()
        else:
            ret = mac_utils._available_services()

        # Make sure it's a dict with 8 items
        self.assertTrue(isinstance(ret, dict))
        self.assertEqual(len(ret), 8)

        self.assertEqual(
            ret['com.apple.lla1']['file_name'],
            'com.apple.lla1.plist')

        self.assertEqual(
            ret['com.apple.lla1']['file_path'],
            os.path.realpath(
                os.path.join('/Library/LaunchAgents', 'com.apple.lla1.plist')))

        self.assertEqual(
            ret['com.apple.slld2']['file_name'],
            'com.apple.slld2.plist')

        self.assertEqual(
            ret['com.apple.slld2']['file_path'],
            os.path.realpath(
                os.path.join('/System/Library/LaunchDaemons', 'com.apple.slld2.plist')))

    @patch('salt.utils.path.os_walk')
    @patch('os.path.exists')
    @patch('plistlib.readPlist' if six.PY2 else 'plistlib.load')
    def test_available_services_broken_symlink(self, mock_read_plist, mock_exists, mock_os_walk):
        '''
        test available_services
        '''
        def walk_side_effect(*args, **kwargs):
            path = args[0]
            results = {
                '/Library/LaunchAgents': ['com.apple.lla1.plist', 'com.apple.lla2.plist'],
                '/Library/LaunchDaemons': ['com.apple.lld1.plist', 'com.apple.lld2.plist'],
                '/System/Library/LaunchAgents': ['com.apple.slla1.plist', 'com.apple.slla2.plist'],
                '/System/Library/LaunchDaemons': ['com.apple.slld1.plist', 'com.apple.slld2.plist']}
            files = results.get(path, [])
            return [(path, [], files)]

        mock_os_walk.side_effect = walk_side_effect

        mock_read_plist.side_effect = [
            MagicMock(Label='com.apple.lla1'),
            MagicMock(Label='com.apple.lla2'),
            MagicMock(Label='com.apple.lld1'),
            MagicMock(Label='com.apple.lld2'),
            MagicMock(Label='com.apple.slld1'),
            MagicMock(Label='com.apple.slld2'),
        ]

        mock_exists.side_effect = [True, True, True, True, False, False, True, True]
        if six.PY3:
            # Py3's plistlib.load does not handle opening and closing a
            # file, unlike py2's plistlib.readPlist. Therefore, we have
            # to patch open for py3 since we're using it in addition
            # to the plistlib.load call.
            with patch('salt.utils.files.fopen', mock_open()):
                ret = mac_utils._available_services()
        else:
            ret = mac_utils._available_services()

        # Make sure it's a dict with 6 items
        self.assertTrue(isinstance(ret, dict))
        self.assertEqual(len(ret), 6)

        self.assertEqual(
            ret['com.apple.lla1']['file_name'],
            'com.apple.lla1.plist')

        self.assertEqual(
            ret['com.apple.lla1']['file_path'],
            os.path.realpath(
                os.path.join('/Library/LaunchAgents', 'com.apple.lla1.plist')))

        self.assertEqual(
            ret['com.apple.slld2']['file_name'],
            'com.apple.slld2.plist')

        self.assertEqual(
            ret['com.apple.slld2']['file_path'],
            os.path.realpath(
                os.path.join('/System/Library/LaunchDaemons', 'com.apple.slld2.plist')))

    @patch('salt.utils.path.os_walk')
    @patch('os.path.exists')
    @patch('plistlib.readPlist')
    @patch('salt.utils.mac_utils.__salt__')
    @patch('plistlib.readPlistFromString' if six.PY2 else 'plistlib.loads')
    def test_available_services_non_xml(self,
                                        mock_read_plist_from_string,
                                        mock_run,
                                        mock_read_plist,
                                        mock_exists,
                                        mock_os_walk):
        '''
        test available_services
        '''
        def walk_side_effect(*args, **kwargs):
            path = args[0]
            results = {
                '/Library/LaunchAgents': ['com.apple.lla1.plist', 'com.apple.lla2.plist'],
                '/Library/LaunchDaemons': ['com.apple.lld1.plist', 'com.apple.lld2.plist'],
                '/System/Library/LaunchAgents': ['com.apple.slla1.plist', 'com.apple.slla2.plist'],
                '/System/Library/LaunchDaemons': ['com.apple.slld1.plist', 'com.apple.slld2.plist']}
            files = results.get(path, [])
            return [(path, [], files)]

        mock_os_walk.side_effect = walk_side_effect
        attrs = {'cmd.run': MagicMock(return_value='<some xml>')}

        def getitem(name):
            return attrs[name]

        mock_run.__getitem__.side_effect = getitem
        mock_run.configure_mock(**attrs)
        mock_exists.return_value = True
        mock_read_plist.side_effect = Exception()
        mock_read_plist_from_string.side_effect = [
            MagicMock(Label='com.apple.lla1'),
            MagicMock(Label='com.apple.lla2'),
            MagicMock(Label='com.apple.lld1'),
            MagicMock(Label='com.apple.lld2'),
            MagicMock(Label='com.apple.slla1'),
            MagicMock(Label='com.apple.slla2'),
            MagicMock(Label='com.apple.slld1'),
            MagicMock(Label='com.apple.slld2'),
        ]

        ret = mac_utils._available_services()

        cmd = '/usr/bin/plutil -convert xml1 -o - -- "{0}"'
        calls = [
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/Library/LaunchAgents', 'com.apple.lla1.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/Library/LaunchAgents', 'com.apple.lla2.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/Library/LaunchDaemons', 'com.apple.lld1.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/Library/LaunchDaemons', 'com.apple.lld2.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/System/Library/LaunchAgents', 'com.apple.slla1.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/System/Library/LaunchAgents', 'com.apple.slla2.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/System/Library/LaunchDaemons', 'com.apple.slld1.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/System/Library/LaunchDaemons', 'com.apple.slld2.plist'))),),
        ]
        mock_run.assert_has_calls(calls, any_order=True)

        # Make sure it's a dict with 8 items
        self.assertTrue(isinstance(ret, dict))
        self.assertEqual(len(ret), 8)

        self.assertEqual(
            ret['com.apple.lla1']['file_name'],
            'com.apple.lla1.plist')

        self.assertEqual(
            ret['com.apple.lla1']['file_path'],
            os.path.realpath(
                os.path.join('/Library/LaunchAgents', 'com.apple.lla1.plist')))

        self.assertEqual(
            ret['com.apple.slld2']['file_name'],
            'com.apple.slld2.plist')

        self.assertEqual(
            ret['com.apple.slld2']['file_path'],
            os.path.realpath(
                os.path.join('/System/Library/LaunchDaemons', 'com.apple.slld2.plist')))

    @patch('salt.utils.path.os_walk')
    @patch('os.path.exists')
    @patch('plistlib.readPlist')
    @patch('salt.utils.mac_utils.__salt__')
    @patch('plistlib.readPlistFromString' if six.PY2 else 'plistlib.loads')
    def test_available_services_non_xml_malformed_plist(self,
                                                        mock_read_plist_from_string,
                                                        mock_run,
                                                        mock_read_plist,
                                                        mock_exists,
                                                        mock_os_walk):
        '''
        test available_services
        '''
        def walk_side_effect(*args, **kwargs):
            path = args[0]
            results = {
                '/Library/LaunchAgents': ['com.apple.lla1.plist', 'com.apple.lla2.plist'],
                '/Library/LaunchDaemons': ['com.apple.lld1.plist', 'com.apple.lld2.plist'],
                '/System/Library/LaunchAgents': ['com.apple.slla1.plist', 'com.apple.slla2.plist'],
                '/System/Library/LaunchDaemons': ['com.apple.slld1.plist', 'com.apple.slld2.plist']}
            files = results.get(path, [])
            return [(path, [], files)]

        mock_os_walk.side_effect = walk_side_effect
        attrs = {'cmd.run': MagicMock(return_value='<some xml>')}

        def getitem(name):
            return attrs[name]

        mock_run.__getitem__.side_effect = getitem
        mock_run.configure_mock(**attrs)
        mock_exists.return_value = True
        mock_read_plist.side_effect = Exception()
        mock_read_plist_from_string.return_value = 'malformedness'

        ret = mac_utils._available_services()

        cmd = '/usr/bin/plutil -convert xml1 -o - -- "{0}"'
        calls = [
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/Library/LaunchAgents', 'com.apple.lla1.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/Library/LaunchAgents', 'com.apple.lla2.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/Library/LaunchDaemons', 'com.apple.lld1.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/Library/LaunchDaemons', 'com.apple.lld2.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/System/Library/LaunchAgents', 'com.apple.slla1.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/System/Library/LaunchAgents', 'com.apple.slla2.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/System/Library/LaunchDaemons', 'com.apple.slld1.plist'))),),
            call.cmd.run(cmd.format(os.path.realpath(os.path.join(
                         '/System/Library/LaunchDaemons', 'com.apple.slld2.plist'))),),
        ]
        mock_run.assert_has_calls(calls, any_order=True)

        # Make sure it's a dict with 8 items
        self.assertTrue(isinstance(ret, dict))
        self.assertEqual(len(ret), 8)

        self.assertEqual(
            ret['com.apple.lla1.plist']['file_name'],
            'com.apple.lla1.plist')

        self.assertEqual(
            ret['com.apple.lla1.plist']['file_path'],
            os.path.realpath(
                os.path.join('/Library/LaunchAgents', 'com.apple.lla1.plist')))

        self.assertEqual(
            ret['com.apple.slld2.plist']['file_name'],
            'com.apple.slld2.plist')

        self.assertEqual(
            ret['com.apple.slld2.plist']['file_path'],
            os.path.realpath(
                os.path.join('/System/Library/LaunchDaemons', 'com.apple.slld2.plist')))
