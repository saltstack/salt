import getpass
import logging
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

    def setUp(self):
        self.logger = logging.getLogger(__name__)

    def test_zmq_verify(self):
        self.assertTrue(zmq_version())

    def test_zmq_verify_insuficient(self):
        import zmq
        zmq.__version__ = '2.1.0'
        self.assertFalse(zmq_version())

    def test_user(self):
        self.assertTrue(check_user(getpass.getuser(), self.logger))

    def test_no_user(self):
        self.assertFalse(check_user('nouser', self.logger))

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
