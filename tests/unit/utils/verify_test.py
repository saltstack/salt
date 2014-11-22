# -*- coding: utf-8 -*-
'''
Test the verification routines
'''

# Import Python libs
from __future__ import absolute_import
import getpass
import os
import sys
import stat
import shutil
import resource
import tempfile
import socket

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import (
    ensure_in_syspath,
    requires_network,
    TestsLoggingHandler
)
ensure_in_syspath('../../')

# Import salt libs
import salt.utils
import integration
from salt.utils.verify import (
    check_user,
    verify_env,
    verify_socket,
    zmq_version,
    check_max_open_files,
    valid_id
)

# Import 3rd-party libs
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

    def test_zmq_verify(self):
        self.assertTrue(zmq_version())

    def test_zmq_verify_insufficient(self):
        import zmq
        zmq.__version__ = '2.1.0'
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
        self.assertFalse(check_user('nouser'))
        # Restore sys.stderr
        sys.stderr = stderr
        if writer.output != 'CRITICAL: User not found: "nouser"\n':
            # If there's a different error catch, write it to sys.stderr
            sys.stderr.write(writer.output)

    @skipIf(sys.platform.startswith('win'), 'No verify_env Windows')
    def test_verify_env(self):
        root_dir = tempfile.mkdtemp(dir=integration.SYS_TMP_DIR)
        var_dir = os.path.join(root_dir, 'var', 'log', 'salt')
        verify_env([var_dir], getpass.getuser())
        self.assertTrue(os.path.exists(var_dir))
        dir_stat = os.stat(var_dir)
        self.assertEqual(dir_stat.st_uid, os.getuid())
        self.assertEqual(dir_stat.st_gid, os.getgid())
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

    @skipIf(True, 'Skipping until we can find why Jenkins is bailing out')
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

            mof_s, mof_h = resource.getrlimit(resource.RLIMIT_NOFILE)
            tempdir = tempfile.mkdtemp(prefix='fake-keys')
            keys_dir = os.path.join(tempdir, 'minions')
            os.makedirs(keys_dir)

            mof_test = 256

            resource.setrlimit(resource.RLIMIT_NOFILE, (mof_test, mof_h))

            try:
                prev = 0
                for newmax, level in ((24, None), (66, 'INFO'),
                                      (127, 'WARNING'), (196, 'CRITICAL')):

                    for n in range(prev, newmax):
                        kpath = os.path.join(keys_dir, str(n))
                        with salt.utils.fopen(kpath, 'w') as fp_:
                            fp_.write(str(n))

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
                                mof_h - newmax,
                            ),
                            handler.messages
                        )
                    handler.clear()
                    prev = newmax

                newmax = mof_test
                for n in range(prev, newmax):
                    kpath = os.path.join(keys_dir, str(n))
                    with salt.utils.fopen(kpath, 'w') as fp_:
                        fp_.write(str(n))

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
                        mof_h - newmax,
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
                shutil.rmtree(tempdir)
                resource.setrlimit(resource.RLIMIT_NOFILE, (mof_s, mof_h))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestVerify, needs_daemon=False)
