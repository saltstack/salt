# -*- coding: utf-8 -*-
'''
tests.unit.api_config_test
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.helpers import destructiveTest
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt libs
import salt.config
import salt.utils

MOCK_MASTER_DEFAULT_OPTS = {
    'log_file': '/var/log/salt/master',
    'pidfile': '/var/run/salt-master.pid',
    'root_dir': '/'
}
if salt.utils.is_windows():
    MOCK_MASTER_DEFAULT_OPTS = {
        'log_file': 'c:\\salt\\var\\log\\salt\\master',
        'pidfile': 'c:\\salt\\var\\run\\salt-master.pid',
        'root_dir': 'c:\\salt'
    }


@skipIf(NO_MOCK, NO_MOCK_REASON)
class APIConfigTestCase(TestCase):
    '''
    TestCase for the api_config function in salt.config.__init__.py
    '''

    def test_api_config_log_file_values(self):
        '''
        Tests the opts value of the 'log_file' after running through the
        various default dict updates. 'log_file' should be updated to match
        the DEFAULT_API_OPTS 'api_logfile' value.
        '''
        with patch('salt.config.client_config', MagicMock(return_value=MOCK_MASTER_DEFAULT_OPTS)):

            expected = '/var/log/salt/api'
            if salt.utils.is_windows():
                expected = 'c:\\salt\\var\\log\\salt\\api'

            ret = salt.config.api_config('/some/fake/path')
            self.assertEqual(ret['log_file'], expected)

    def test_api_config_pidfile_values(self):
        '''
        Tests the opts value of the 'pidfile' after running through the
        various default dict updates. 'pidfile' should be updated to match
        the DEFAULT_API_OPTS 'api_pidfile' value.
        '''
        with patch('salt.config.client_config', MagicMock(return_value=MOCK_MASTER_DEFAULT_OPTS)):

            expected = '/var/run/salt-api.pid'
            if salt.utils.is_windows():
                expected = 'c:\\salt\\var\\run\\salt-api.pid'

            ret = salt.config.api_config('/some/fake/path')
            self.assertEqual(ret['pidfile'], expected)

    @destructiveTest
    def test_master_config_file_overrides_defaults(self):
        '''
        Tests the opts value of the api config values after running through the
        various default dict updates that should be overridden by settings in
        the user's master config file.
        '''
        # Copy DEFAULT_API_OPTS to restore after the test
        default_api_opts = salt.config.DEFAULT_API_OPTS.copy()

        foo_dir = '/foo/bar/baz'
        hello_dir = '/hello/world'
        if salt.utils.is_windows():
            foo_dir = 'c:\\foo\\bar\\baz'
            hello_dir = 'c:\\hello\\world'

        mock_master_config = {
            'api_pidfile': foo_dir,
            'api_logfile': hello_dir,
            'rest_timeout': 5
        }
        mock_master_config.update(MOCK_MASTER_DEFAULT_OPTS.copy())

        with patch('salt.config.client_config',
                   MagicMock(return_value=mock_master_config)):
            ret = salt.config.api_config('/some/fake/path')
            self.assertEqual(ret['rest_timeout'], 5)
            self.assertEqual(ret['api_pidfile'], foo_dir)
            self.assertEqual(ret['pidfile'], foo_dir)
            self.assertEqual(ret['api_logfile'], hello_dir)
            self.assertEqual(ret['log_file'], hello_dir)

        # Reset DEFAULT_API_OPTS settings as to not interfere with other unit tests
        salt.config.DEFAULT_API_OPTS = default_api_opts

    @destructiveTest
    def test_api_config_prepend_root_dirs_return(self):
        '''
        Tests the opts value of the api_logfile, log_file, api_pidfile, and pidfile
        when a custom root directory is used. This ensures that each of these
        values is present in the list of opts keys that should have the root_dir
        prepended when the api_config function returns the opts dictionary.
        '''
        # Copy DEFAULT_API_OPTS to restore after the test
        default_api_opts = salt.config.DEFAULT_API_OPTS.copy()

        mock_log = '/mock/root/var/log/salt/api'
        mock_pid = '/mock/root/var/run/salt-api.pid'

        mock_master_config = MOCK_MASTER_DEFAULT_OPTS.copy()
        mock_master_config['root_dir'] = '/mock/root/'

        if salt.utils.is_windows():
            mock_log = 'c:\\mock\\root\\var\\log\\salt\\api'
            mock_pid = 'c:\\mock\\root\\var\\run\\salt-api.pid'
            mock_master_config['root_dir'] = 'c:\\mock\\root'

        with patch('salt.config.client_config',
                   MagicMock(return_value=mock_master_config)):
            ret = salt.config.api_config('/some/fake/path')
            self.assertEqual(ret['api_logfile'], mock_log)
            self.assertEqual(ret['log_file'], mock_log)
            self.assertEqual(ret['api_pidfile'], mock_pid)
            self.assertEqual(ret['pidfile'], mock_pid)

        # Reset DEFAULT_API_OPTS settings as to not interfere with other unit tests
        salt.config.DEFAULT_API_OPTS = default_api_opts
