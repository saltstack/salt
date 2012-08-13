import getpass
import os
import sys
import stat
import tempfile

from saltunittest import skipIf, TestCase

from salt.utils.verify import (
    check_user,
    verify_env,
    verify_socket,
    zmq_version,
)


class TestVerify(TestCase):

    def test_zmq_verify(self):
        self.assertTrue(zmq_version())

    def test_zmq_verify_insuficient(self):
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
        root_dir = tempfile.mkdtemp()
        var_dir = os.path.join(root_dir, 'var', 'log', 'salt')
        verify_env([var_dir], getpass.getuser())
        self.assertTrue(os.path.exists(var_dir))
        dir_stat = os.stat(var_dir)
        self.assertEqual(dir_stat.st_uid, os.getuid())
        self.assertEqual(dir_stat.st_gid, os.getgid())
        self.assertEqual(dir_stat.st_mode & stat.S_IRWXU, stat.S_IRWXU)
        self.assertEqual(dir_stat.st_mode & stat.S_IRWXG, 0)
        self.assertEqual(dir_stat.st_mode & stat.S_IRWXO, 0)

    def test_verify_socket(self):
        self.assertTrue(verify_socket('', 18000, 18001))
