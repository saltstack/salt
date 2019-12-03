# -*- coding: utf-8 -*-
'''
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import tempfile

# Import Salt Libs
import salt.utils.files
import salt.utils.platform
import salt.modules.cmdmod as cmdmod
from salt.exceptions import CommandExecutionError
from salt.log import LOG_LEVELS
from salt.ext.six.moves import builtins  # pylint: disable=import-error

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.paths import FILES
from tests.support.mock import (
    mock_open,
    Mock,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

DEFAULT_SHELL = 'foo/bar'
MOCK_SHELL_FILE = '# List of acceptable shells\n' \
                  '\n'\
                  '/bin/bash\n'


class MockTimedProc(object):
    '''
    Class used as a stand-in for salt.utils.timed_subprocess.TimedProc
    '''
    class _Process(object):
        '''
        Used to provide a dummy "process" attribute
        '''
        def __init__(self, returncode=0, pid=12345):
            self.returncode = returncode
            self.pid = pid

    def __init__(self, stdout=None, stderr=None, returncode=0, pid=12345):
        if stdout is not None and not isinstance(stdout, bytes):
            raise TypeError('Must pass stdout to MockTimedProc as bytes')
        if stderr is not None and not isinstance(stderr, bytes):
            raise TypeError('Must pass stderr to MockTimedProc as bytes')
        self._stdout = stdout
        self._stderr = stderr
        self.process = self._Process(returncode=returncode, pid=pid)

    def run(self):
        pass

    @property
    def stdout(self):
        return self._stdout

    @property
    def stderr(self):
        return self._stderr


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

    def test_run_shell_is_not_file(self):
        '''
        Tests error raised when shell is not available after _is_valid_shell error msg
        and os.path.isfile returns False
        '''
        with patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True)):
            with patch('salt.utils.platform.is_windows', MagicMock(return_value=False)):
                with patch('os.path.isfile', MagicMock(return_value=False)):
                    self.assertRaises(CommandExecutionError, cmdmod._run, 'foo', 'bar')

    def test_run_shell_file_no_access(self):
        '''
        Tests error raised when shell is not available after _is_valid_shell error msg,
        os.path.isfile returns True, but os.access returns False
        '''
        with patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True)):
            with patch('salt.utils.platform.is_windows', MagicMock(return_value=False)):
                with patch('os.path.isfile', MagicMock(return_value=True)):
                    with patch('os.access', MagicMock(return_value=False)):
                        self.assertRaises(CommandExecutionError, cmdmod._run, 'foo', 'bar')

    def test_run_runas_with_windows(self):
        '''
        Tests error raised when runas is passed on windows
        '''
        with patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True)):
            with patch('salt.utils.platform.is_windows', MagicMock(return_value=True)):
                with patch.dict(cmdmod.__grains__, {'os': 'fake_os'}):
                    self.assertRaises(CommandExecutionError,
                                      cmdmod._run,
                                      'foo', 'bar', runas='baz')

    def test_run_user_not_available(self):
        '''
        Tests return when runas user is not available
        '''
        mock_true = MagicMock(return_value=True)
        with patch('salt.modules.cmdmod._is_valid_shell', mock_true), \
                patch('os.path.isfile', mock_true), \
                patch('os.access', mock_true):
            self.assertRaises(CommandExecutionError,
                              cmdmod._run, 'foo', 'bar', runas='baz')

    def test_run_zero_umask(self):
        '''
        Tests error raised when umask is set to zero
        '''
        with patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True)):
            with patch('salt.utils.platform.is_windows', MagicMock(return_value=False)):
                with patch('os.path.isfile', MagicMock(return_value=True)):
                    with patch('os.access', MagicMock(return_value=True)):
                        self.assertRaises(CommandExecutionError, cmdmod._run, 'foo', 'bar', umask=0)

    def test_run_invalid_umask(self):
        '''
        Tests error raised when an invalid umask is given
        '''
        with patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True)):
            with patch('salt.utils.platform.is_windows', MagicMock(return_value=False)):
                with patch('os.path.isfile', MagicMock(return_value=True)):
                    with patch('os.access', MagicMock(return_value=True)):
                        self.assertRaises(CommandExecutionError, cmdmod._run, 'foo', 'bar', umask='baz')

    def test_run_invalid_cwd_not_abs_path(self):
        '''
        Tests error raised when cwd is not an absolute path
        '''
        with patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True)):
            with patch('salt.utils.platform.is_windows', MagicMock(return_value=False)):
                with patch('os.path.isfile', MagicMock(return_value=True)):
                    with patch('os.access', MagicMock(return_value=True)):
                        self.assertRaises(CommandExecutionError, cmdmod._run, 'foo', 'bar')

    def test_run_invalid_cwd_not_dir(self):
        '''
        Tests error raised when cwd is not a dir
        '''
        with patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True)):
            with patch('salt.utils.platform.is_windows', MagicMock(return_value=False)):
                with patch('os.path.isfile', MagicMock(return_value=True)):
                    with patch('os.access', MagicMock(return_value=True)):
                        with patch('os.path.isabs', MagicMock(return_value=True)):
                            self.assertRaises(CommandExecutionError, cmdmod._run, 'foo', 'bar')

    def test_run_no_vt_os_error(self):
        '''
        Tests error raised when not useing vt and OSError is provided
        '''
        expected_error = "expect error"
        with patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True)):
            with patch('salt.utils.platform.is_windows', MagicMock(return_value=False)):
                with patch('os.path.isfile', MagicMock(return_value=True)):
                    with patch('os.access', MagicMock(return_value=True)):
                        with patch('salt.utils.timed_subprocess.TimedProc', MagicMock(side_effect=OSError(expected_error))):
                            with self.assertRaises(CommandExecutionError) as error:
                                cmdmod.run('foo')
                            assert error.exception.args[0].endswith(expected_error), repr(error.exception.args[0])

    def test_run_no_vt_io_error(self):
        '''
        Tests error raised when not useing vt and IOError is provided
        '''
        expected_error = "expect error"
        with patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True)):
            with patch('salt.utils.platform.is_windows', MagicMock(return_value=False)):
                with patch('os.path.isfile', MagicMock(return_value=True)):
                    with patch('os.access', MagicMock(return_value=True)):
                        with patch('salt.utils.timed_subprocess.TimedProc', MagicMock(side_effect=IOError(expected_error))):
                            with self.assertRaises(CommandExecutionError) as error:
                                cmdmod.run('foo')
                            assert error.exception.args[0].endswith(expected_error), repr(error.exception.args[0])

    @skipIf(salt.utils.platform.is_windows(), 'Do not run on Windows')
    @skipIf(True, 'Test breaks unittests runs')
    def test_run(self):
        '''
        Tests end result when a command is not found
        '''
        with patch('salt.modules.cmdmod._is_valid_shell', MagicMock(return_value=True)):
            with patch('salt.utils.platform.is_windows', MagicMock(return_value=False)):
                with patch('os.path.isfile', MagicMock(return_value=True)):
                    with patch('os.access', MagicMock(return_value=True)):
                        ret = cmdmod._run('foo', cwd=os.getcwd(), use_vt=True).get('stderr')
                        self.assertIn('foo', ret)

    def test_is_valid_shell_windows(self):
        '''
        Tests return if running on windows
        '''
        with patch('salt.utils.platform.is_windows', MagicMock(return_value=True)):
            self.assertTrue(cmdmod._is_valid_shell('foo'))

    @skipIf(salt.utils.platform.is_windows(), 'Do not run on Windows')
    def test_is_valid_shell_none(self):
        '''
        Tests return of when os.path.exists(/etc/shells) isn't available
        '''
        with patch('os.path.exists', MagicMock(return_value=False)):
            self.assertIsNone(cmdmod._is_valid_shell('foo'))

    def test_is_valid_shell_available(self):
        '''
        Tests return when provided shell is available
        '''
        with patch('os.path.exists', MagicMock(return_value=True)):
            with patch('salt.utils.files.fopen', mock_open(read_data=MOCK_SHELL_FILE)):
                self.assertTrue(cmdmod._is_valid_shell('/bin/bash'))

    @skipIf(salt.utils.platform.is_windows(), 'Do not run on Windows')
    def test_is_valid_shell_unavailable(self):
        '''
        Tests return when provided shell is not available
        '''
        with patch('os.path.exists', MagicMock(return_value=True)):
            with patch('salt.utils.files.fopen', mock_open(read_data=MOCK_SHELL_FILE)):
                self.assertFalse(cmdmod._is_valid_shell('foo'))

    @skipIf(salt.utils.platform.is_windows(), 'Do not run on Windows')
    def test_os_environment_remains_intact(self):
        '''
        Make sure the OS environment is not tainted after running a command
        that specifies runas.
        '''
        with patch('pwd.getpwnam') as getpwnam_mock:
            with patch('subprocess.Popen') as popen_mock:
                environment = os.environ.copy()

                popen_mock.return_value = Mock(
                    communicate=lambda *args, **kwags: [b'', None],
                    pid=lambda: 1,
                    retcode=0
                )

                with patch.dict(cmdmod.__grains__, {'os': 'Darwin', 'os_family': 'Solaris'}):
                    if sys.platform.startswith(('freebsd', 'openbsd')):
                        shell = '/bin/sh'
                    else:
                        shell = '/bin/bash'

                    cmdmod._run('ls',
                                cwd=tempfile.gettempdir(),
                                runas='foobar',
                                shell=shell)

                    environment2 = os.environ.copy()

                    self.assertEqual(environment, environment2)

                    if not salt.utils.platform.is_darwin():
                        getpwnam_mock.assert_called_with('foobar')

    def test_run_cwd_doesnt_exist_issue_7154(self):
        '''
        cmd.run should fail and raise
        salt.exceptions.CommandExecutionError if the cwd dir does not
        exist
        '''
        cmd = 'echo OHAI'
        cwd = '/path/to/nowhere'
        try:
            cmdmod.run_all(cmd, cwd=cwd)
        except CommandExecutionError:
            pass
        else:
            raise RuntimeError

    def test_run_all_binary_replace(self):
        '''
        Test for failed decoding of binary data, for instance when doing
        something silly like using dd to read from /dev/urandom and write to
        /dev/stdout.
        '''
        # Since we're using unicode_literals, read the random bytes from a file
        rand_bytes_file = os.path.join(FILES, 'file', 'base', 'random_bytes')
        with salt.utils.files.fopen(rand_bytes_file, 'rb') as fp_:
            stdout_bytes = fp_.read()

        # kitchen-salt uses unix2dos on all the files before copying them over
        # to the vm that will be running the tests. It skips binary files though
        # The file specified in `rand_bytes_file` is detected as binary so the
        # Unix-style line ending remains. This should account for that.
        stdout_bytes = stdout_bytes.rstrip() + os.linesep.encode()

        # stdout with the non-decodable bits replaced with the unicode
        # replacement character U+FFFD.
        stdout_unicode = '\ufffd\x1b\ufffd\ufffd' + os.linesep
        stderr_bytes = os.linesep.encode().join([
            b'1+0 records in',
            b'1+0 records out',
            b'4 bytes copied, 9.1522e-05 s, 43.7 kB/s']) + os.linesep.encode()
        stderr_unicode = stderr_bytes.decode()

        proc = MagicMock(
            return_value=MockTimedProc(
                stdout=stdout_bytes,
                stderr=stderr_bytes
            )
        )
        with patch('salt.utils.timed_subprocess.TimedProc', proc):
            ret = cmdmod.run_all(
                'dd if=/dev/urandom of=/dev/stdout bs=4 count=1',
                rstrip=False)

        self.assertEqual(ret['stdout'], stdout_unicode)
        self.assertEqual(ret['stderr'], stderr_unicode)

    def test_run_all_none(self):
        '''
        Tests cases when proc.stdout or proc.stderr are None. These should be
        caught and replaced with empty strings.
        '''
        proc = MagicMock(return_value=MockTimedProc(stdout=None, stderr=None))
        with patch('salt.utils.timed_subprocess.TimedProc', proc):
            ret = cmdmod.run_all('some command', rstrip=False)

        self.assertEqual(ret['stdout'], '')
        self.assertEqual(ret['stderr'], '')

    def test_run_all_unicode(self):
        '''
        Ensure that unicode stdout and stderr are decoded properly
        '''
        stdout_unicode = 'Here is some unicode: спам'
        stderr_unicode = 'Here is some unicode: яйца'
        stdout_bytes = stdout_unicode.encode('utf-8')
        stderr_bytes = stderr_unicode.encode('utf-8')

        proc = MagicMock(
            return_value=MockTimedProc(
                stdout=stdout_bytes,
                stderr=stderr_bytes
            )
        )

        with patch('salt.utils.timed_subprocess.TimedProc', proc), \
                patch.object(builtins, '__salt_system_encoding__', 'utf-8'):
            ret = cmdmod.run_all('some command', rstrip=False)

        self.assertEqual(ret['stdout'], stdout_unicode)
        self.assertEqual(ret['stderr'], stderr_unicode)

    def test_run_all_output_encoding(self):
        '''
        Test that specifying the output encoding works as expected
        '''
        stdout = 'Æ'
        stdout_latin1_enc = stdout.encode('latin1')

        proc = MagicMock(return_value=MockTimedProc(stdout=stdout_latin1_enc))

        with patch('salt.utils.timed_subprocess.TimedProc', proc), \
                patch.object(builtins, '__salt_system_encoding__', 'utf-8'):
            ret = cmdmod.run_all('some command', output_encoding='latin1')

        self.assertEqual(ret['stdout'], stdout)
