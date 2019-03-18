# -*- coding: utf-8 -*-
'''
Test the verification routines
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import getpass
import os
import sys
import stat
import shutil
import tempfile
import socket

# Import third party libs
if sys.platform.startswith('win'):
    import win32file
else:
    import resource

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.paths import TMP
from tests.support.helpers import (
    requires_network,
    TestsLoggingHandler
)
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import salt libs
import salt.utils.files
from salt.utils.verify import (
    check_user,
    verify_env,
    verify_socket,
    zmq_version,
    check_max_open_files,
    valid_id,
    log,
    verify_log,
)

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin


class TestVerify(TestCase):
    '''
    Verify module tests
    '''

    def test_valid_id_exception_handler(self):
        '''
        Ensure we just return False if we pass in invalid or undefined paths.
        Refs #8259
        '''
        opts = {'pki_dir': '/tmp/whatever'}
        self.assertFalse(valid_id(opts, None))

    def test_valid_id_pathsep(self):
        '''
        Path separators in id should make it invalid
        '''
        opts = {'pki_dir': '/tmp/whatever'}
        # We have to test both path separators because os.path.normpath will
        # convert forward slashes to backslashes on Windows.
        for pathsep in ('/', '\\'):
            self.assertFalse(valid_id(opts, pathsep.join(('..', 'foobar'))))

    def test_zmq_verify(self):
        self.assertTrue(zmq_version())

    def test_zmq_verify_insufficient(self):
        import zmq
        with patch.object(zmq, '__version__', '2.1.0'):
            self.assertFalse(zmq_version())

    def test_user(self):
        self.assertTrue(check_user(getpass.getuser()))

    def test_no_user(self):
        # Catch sys.stderr here since no logging is configured and
        # check_user WILL write to sys.stderr
        class FakeWriter(object):
            def __init__(self):
                self.output = ""

            def write(self, data):
                self.output += data
        stderr = sys.stderr
        writer = FakeWriter()
        sys.stderr = writer
        # Now run the test
        if sys.platform.startswith('win'):
            self.assertTrue(check_user('nouser'))
        else:
            self.assertFalse(check_user('nouser'))
        # Restore sys.stderr
        sys.stderr = stderr
        if writer.output != 'CRITICAL: User not found: "nouser"\n':
            # If there's a different error catch, write it to sys.stderr
            sys.stderr.write(writer.output)

    @skipIf(sys.platform.startswith('win'), 'No verify_env Windows')
    def test_verify_env(self):
        root_dir = tempfile.mkdtemp(dir=TMP)
        var_dir = os.path.join(root_dir, 'var', 'log', 'salt')
        key_dir = os.path.join(root_dir, 'key_dir')
        verify_env([var_dir], getpass.getuser(), root_dir=root_dir)
        self.assertTrue(os.path.exists(var_dir))
        dir_stat = os.stat(var_dir)
        self.assertEqual(dir_stat.st_uid, os.getuid())
        self.assertEqual(dir_stat.st_mode & stat.S_IRWXU, stat.S_IRWXU)
        self.assertEqual(dir_stat.st_mode & stat.S_IRWXG, 40)
        self.assertEqual(dir_stat.st_mode & stat.S_IRWXO, 5)

    @requires_network(only_local_network=True)
    def test_verify_socket(self):
        self.assertTrue(verify_socket('', 18000, 18001))
        if socket.has_ipv6:
            # Only run if Python is built with IPv6 support; otherwise
            # this will just fail.
            try:
                self.assertTrue(verify_socket('::', 18000, 18001))
            except socket.error as serr:
                # Python has IPv6 enabled, but the system cannot create
                # IPv6 sockets (otherwise the test would return a bool)
                # - skip the test
                #
                # FIXME - possibly emit a message that the system does
                # not support IPv6.
                pass

    def test_max_open_files(self):
        with TestsLoggingHandler() as handler:
            logmsg_dbg = (
                'DEBUG:This salt-master instance has accepted {0} minion keys.'
            )
            logmsg_chk = (
                '{0}:The number of accepted minion keys({1}) should be lower '
                'than 1/4 of the max open files soft setting({2}). According '
                'to the system\'s hard limit, there\'s still a margin of {3} '
                'to raise the salt\'s max_open_files setting. Please consider '
                'raising this value.'
            )
            logmsg_crash = (
                '{0}:The number of accepted minion keys({1}) should be lower '
                'than 1/4 of the max open files soft setting({2}). '
                'salt-master will crash pretty soon! According to the '
                'system\'s hard limit, there\'s still a margin of {3} to '
                'raise the salt\'s max_open_files setting. Please consider '
                'raising this value.'
            )
            if sys.platform.startswith('win'):
                logmsg_crash = (
                    '{0}:The number of accepted minion keys({1}) should be lower '
                    'than 1/4 of the max open files soft setting({2}). '
                    'salt-master will crash pretty soon! Please consider '
                    'raising this value.'
                )

            if sys.platform.startswith('win'):
                # Check the Windows API for more detail on this
                # http://msdn.microsoft.com/en-us/library/xt874334(v=vs.71).aspx
                # and the python binding http://timgolden.me.uk/pywin32-docs/win32file.html
                mof_s = mof_h = win32file._getmaxstdio()
            else:
                mof_s, mof_h = resource.getrlimit(resource.RLIMIT_NOFILE)
            tempdir = tempfile.mkdtemp(prefix='fake-keys')
            keys_dir = os.path.join(tempdir, 'minions')
            os.makedirs(keys_dir)

            mof_test = 256

            if sys.platform.startswith('win'):
                win32file._setmaxstdio(mof_test)
            else:
                resource.setrlimit(resource.RLIMIT_NOFILE, (mof_test, mof_h))

            try:
                prev = 0
                for newmax, level in ((24, None), (66, 'INFO'),
                                      (127, 'WARNING'), (196, 'CRITICAL')):

                    for n in range(prev, newmax):
                        kpath = os.path.join(keys_dir, six.text_type(n))
                        with salt.utils.files.fopen(kpath, 'w') as fp_:
                            fp_.write(str(n))  # future lint: disable=blacklisted-function

                    opts = {
                        'max_open_files': newmax,
                        'pki_dir': tempdir
                    }

                    check_max_open_files(opts)

                    if level is None:
                        # No log message is triggered, only the DEBUG one which
                        # tells us how many minion keys were accepted.
                        self.assertEqual(
                            [logmsg_dbg.format(newmax)], handler.messages
                        )
                    else:
                        self.assertIn(
                            logmsg_dbg.format(newmax), handler.messages
                        )
                        self.assertIn(
                            logmsg_chk.format(
                                level,
                                newmax,
                                mof_test,
                                mof_test - newmax if sys.platform.startswith('win') else mof_h - newmax,
                            ),
                            handler.messages
                        )
                    handler.clear()
                    prev = newmax

                newmax = mof_test
                for n in range(prev, newmax):
                    kpath = os.path.join(keys_dir, six.text_type(n))
                    with salt.utils.files.fopen(kpath, 'w') as fp_:
                        fp_.write(str(n))  # future lint: disable=blacklisted-function

                opts = {
                    'max_open_files': newmax,
                    'pki_dir': tempdir
                }

                check_max_open_files(opts)
                self.assertIn(logmsg_dbg.format(newmax), handler.messages)
                self.assertIn(
                    logmsg_crash.format(
                        'CRITICAL',
                        newmax,
                        mof_test,
                        mof_test - newmax if sys.platform.startswith('win') else mof_h - newmax,
                    ),
                    handler.messages
                )
                handler.clear()
            except IOError as err:
                if err.errno == 24:
                    # Too many open files
                    self.skipTest('We\'ve hit the max open files setting')
                raise
            finally:
                if sys.platform.startswith('win'):
                    win32file._setmaxstdio(mof_h)
                else:
                    resource.setrlimit(resource.RLIMIT_NOFILE, (mof_s, mof_h))
                shutil.rmtree(tempdir)

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_verify_log(self):
        '''
        Test that verify_log works as expected
        '''
        message = 'Insecure logging configuration detected! Sensitive data may be logged.'

        mock_cheese = MagicMock()
        with patch.object(log, 'warning', mock_cheese):
            verify_log({'log_level': 'cheeseshop'})
            mock_cheese.assert_called_once_with(message)

        mock_trace = MagicMock()
        with patch.object(log, 'warning', mock_trace):
            verify_log({'log_level': 'trace'})
            mock_trace.assert_called_once_with(message)

        mock_none = MagicMock()
        with patch.object(log, 'warning', mock_none):
            verify_log({})
            mock_none.assert_called_once_with(message)

        mock_info = MagicMock()
        with patch.object(log, 'warning', mock_info):
            verify_log({'log_level': 'info'})
            self.assertTrue(mock_info.call_count == 0)
