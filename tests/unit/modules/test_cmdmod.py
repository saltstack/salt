# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.modules.cmdmod as cmdmod
from salt.exceptions import CommandExecutionError
from salt.log import LOG_LEVELS
import salt.utils

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    mock_open,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

DEFAULT_SHELL = 'foo/bar'
MOCK_SHELL_FILE = '# List of acceptable shells\n' \
                  '\n'\
                  '/bin/bash\n'


@skipIf(NO_MOCK, NO_MOCK_REASON)
class CMDMODTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Unit tests for the salt.modules.cmdmod module
    '''

    def setup_loader_modules(self):
        return {cmdmod: {}}

    @classmethod
    def setUpClass(cls):
        cls.mock_loglevels = {'info': 'foo', 'all': 'bar', 'critical': 'bar',
                              'trace': 'bar', 'garbage': 'bar', 'error': 'bar',
                              'debug': 'bar', 'warning': 'bar', 'quiet': 'bar'}

    @classmethod
    def tearDownClass(cls):
        del cls.mock_loglevels

    def test_render_cmd_no_template(self):
        '''
        Tests return when template=None
        '''
        self.assertEqual(cmdmod._render_cmd('foo', 'bar', None),
                         ('foo', 'bar'))

    def test_render_cmd_unavailable_engine(self):
        '''
        Tests CommandExecutionError raised when template isn't in the
        template registry
        '''
        self.assertRaises(CommandExecutionError,
                          cmdmod._render_cmd,
                          'boo', 'bar', 'baz')

    def test_check_loglevel_bad_level(self):
        '''
        Tests return of providing an invalid loglevel option
        '''
        with patch.dict(LOG_LEVELS, self.mock_loglevels):
            self.assertEqual(cmdmod._check_loglevel(level='bad_loglevel'), 'foo')

    def test_check_loglevel_bad_level_not_str(self):
        '''
        Tests the return of providing an invalid loglevel option that is not a string
        '''
        with patch.dict(LOG_LEVELS, self.mock_loglevels):
            self.assertEqual(cmdmod._check_loglevel(level=1000), 'foo')

    def test_check_loglevel_quiet(self):
        '''
        Tests the return of providing a loglevel of 'quiet'
        '''
        with patch.dict(LOG_LEVELS, self.mock_loglevels):
            self.assertEqual(cmdmod._check_loglevel(level='quiet'), None)

    def test_check_loglevel_utils_quite(self):
        '''
        Tests the return of quiet=True
        '''
        with patch.dict(LOG_LEVELS, self.mock_loglevels):
            self.assertEqual(cmdmod._check_loglevel(quiet=True), None)

    def test_parse_env_not_env(self):
        '''
        Tests the return of an env that is not an env
        '''
        self.assertEqual(cmdmod._parse_env(None), {})

    def test_parse_env_list(self):
        '''
        Tests the return of an env that is a list
        '''
        ret = {'foo': None, 'bar': None}
        self.assertEqual(ret, cmdmod._parse_env(['foo', 'bar']))

    def test_parse_env_dict(self):
        '''
        Test the return of an env that is not a dict
        '''
        self.assertEqual(cmdmod._parse_env('test'), {})

    @patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True))
    @patch('salt.utils.is_windows', MagicMock(return_value=False))
    @patch('os.path.isfile', MagicMock(return_value=False))
    def test_run_shell_is_not_file(self):
        '''
        Tests error raised when shell is not available after _is_valid_shell error msg
        and os.path.isfile returns False
        '''
        self.assertRaises(CommandExecutionError, cmdmod._run, 'foo', 'bar')

    @patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True))
    @patch('salt.utils.is_windows', MagicMock(return_value=False))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.access', MagicMock(return_value=False))
    def test_run_shell_file_no_access(self):
        '''
        Tests error raised when shell is not available after _is_valid_shell error msg,
        os.path.isfile returns True, but os.access returns False
        '''
        self.assertRaises(CommandExecutionError, cmdmod._run, 'foo', 'bar')

    @patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True))
    @patch('salt.utils.is_windows', MagicMock(return_value=True))
    def test_run_runas_with_windows(self):
        '''
        Tests error raised when runas is passed on windows
        '''
        with patch.dict(cmdmod.__grains__, {'os': 'fake_os'}):
            self.assertRaises(CommandExecutionError,
                              cmdmod._run,
                              'foo', 'bar', runas='baz')

    @patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.access', MagicMock(return_value=True))
    def test_run_user_not_available(self):
        '''
        Tests return when runas user is not available
        '''
        self.assertRaises(CommandExecutionError, cmdmod._run, 'foo', 'bar', runas='baz')

    @patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True))
    @patch('salt.utils.is_windows', MagicMock(return_value=False))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.access', MagicMock(return_value=True))
    def test_run_zero_umask(self):
        '''
        Tests error raised when umask is set to zero
        '''
        self.assertRaises(CommandExecutionError, cmdmod._run, 'foo', 'bar', umask=0)

    @patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True))
    @patch('salt.utils.is_windows', MagicMock(return_value=False))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.access', MagicMock(return_value=True))
    def test_run_invalid_umask(self):
        '''
        Tests error raised when an invalid umask is given
        '''
        self.assertRaises(CommandExecutionError, cmdmod._run, 'foo', 'bar', umask='baz')

    @patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True))
    @patch('salt.utils.is_windows', MagicMock(return_value=False))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.access', MagicMock(return_value=True))
    def test_run_invalid_cwd_not_abs_path(self):
        '''
        Tests error raised when cwd is not an absolute path
        '''
        self.assertRaises(CommandExecutionError, cmdmod._run, 'foo', 'bar')

    @patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True))
    @patch('salt.utils.is_windows', MagicMock(return_value=False))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.access', MagicMock(return_value=True))
    @patch('os.path.isabs', MagicMock(return_value=True))
    def test_run_invalid_cwd_not_dir(self):
        '''
        Tests error raised when cwd is not a dir
        '''
        self.assertRaises(CommandExecutionError, cmdmod._run, 'foo', 'bar')

    @patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True))
    @patch('salt.utils.is_windows', MagicMock(return_value=False))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.access', MagicMock(return_value=True))
    @patch('salt.utils.timed_subprocess.TimedProc', MagicMock(side_effect=OSError))
    def test_run_no_vt_os_error(self):
        '''
        Tests error raised when not useing vt and OSError is provided
        '''
        self.assertRaises(CommandExecutionError, cmdmod._run, 'foo')

    @patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True))
    @patch('salt.utils.is_windows', MagicMock(return_value=False))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.access', MagicMock(return_value=True))
    @patch('salt.utils.timed_subprocess.TimedProc', MagicMock(side_effect=IOError))
    def test_run_no_vt_io_error(self):
        '''
        Tests error raised when not useing vt and IOError is provided
        '''
        self.assertRaises(CommandExecutionError, cmdmod._run, 'foo')

    @skipIf(salt.utils.is_windows(), 'Do not run on Windows')
    @patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True))
    @patch('salt.utils.is_windows', MagicMock(return_value=False))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('os.access', MagicMock(return_value=True))
    def test_run(self):
        '''
        Tests end result when a command is not found
        '''
        ret = cmdmod._run('foo', use_vt=True).get('stderr')
        self.assertIn('foo', ret)

    @patch('salt.utils.is_windows', MagicMock(return_value=True))
    def test_is_valid_shell_windows(self):
        '''
        Tests return if running on windows
        '''
        self.assertTrue(cmdmod._is_valid_shell('foo'))

    @skipIf(salt.utils.is_windows(), 'Do not run on Windows')
    @patch('os.path.exists', MagicMock(return_value=False))
    def test_is_valid_shell_none(self):
        '''
        Tests return of when os.path.exists(/etc/shells) isn't available
        '''
        self.assertIsNone(cmdmod._is_valid_shell('foo'))

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_is_valid_shell_available(self):
        '''
        Tests return when provided shell is available
        '''
        with patch('salt.utils.fopen', mock_open(read_data=MOCK_SHELL_FILE)):
            self.assertTrue(cmdmod._is_valid_shell('/bin/bash'))

    @skipIf(salt.utils.is_windows(), 'Do not run on Windows')
    @patch('os.path.exists', MagicMock(return_value=True))
    def test_is_valid_shell_unavailable(self):
        '''
        Tests return when provided shell is not available
        '''
        with patch('salt.utils.fopen', mock_open(read_data=MOCK_SHELL_FILE)):
            self.assertFalse(cmdmod._is_valid_shell('foo'))
