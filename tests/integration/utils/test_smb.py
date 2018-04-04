import getpass
import logging
import os
import signal
import subprocess
import tempfile
import time

import salt.utils.smb

from tests.support.case import TestCase

log = logging.getLogger(__name__)
CONFIG = (
    '[global]\n'
    'workgroup = WORKGROUP\n'
    'interfaces = lo 127.0.0.0/8\n'
    'smb ports = 1445\n'
    'log level = 2\n'
    'map to guest = Bad User\n'
    'enable core files = no\n'
    'passdb backend = smbpasswd\n'
    'smb passwd file = {passwdb}\n'
    'lock directory = {samba_dir}\n'
    'state directory = {samba_dir}\n'
    'cache directory = {samba_dir}\n'
    'pid directory = {samba_dir}\n'
    'private dir = {samba_dir}\n'
    'ncalrpc dir = {samba_dir}\n'
    '\n'
    '[public]\n'
    'path = {public_dir}\n'
    'read only = no\n'
    'guest ok = no\n'
)
TBE = (
    '{}:0:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX:AC8E657F8'
    '3DF82BEEA5D43BDAF7800CC:[U          ]:LCT-507C14C7:'
)


class SmbTestCase(TestCase):
    _smbd = None


    @staticmethod
    def check_pid(pid):
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        else:
            return True

    @classmethod
    def setUpClass(cls):
        tmpdir = tempfile.mkdtemp()
        cls.samba_dir = os.path.join(tmpdir, 'samba')
        cls.public_dir = os.path.join(tmpdir, 'public')
        os.makedirs(cls.samba_dir)
        os.makedirs(cls.public_dir)
        passwdb = os.path.join(tmpdir, 'passwdb')
        cls.username = getpass.getuser()
        with open(passwdb, 'w') as fp:
            fp.write(TBE.format(cls.username))
        samba_conf = os.path.join(tmpdir, 'smb.conf')
        with open(samba_conf, 'w') as fp:
            fp.write(
                CONFIG.format(
                    samba_dir=cls.samba_dir,
                    public_dir=cls.public_dir,
                    passwdb=passwdb,
                )
            )
        cls._smbd = subprocess.Popen(
            '/usr/sbin/smbd -FS -s {}'.format(samba_conf),
            shell=True
        )
        time.sleep(.1)
        pidfile = os.path.join(cls.samba_dir, 'smbd.pid')
        with open(pidfile, 'r') as fp:
            cls._pid = int(fp.read().strip())
        if not cls.check_pid(cls._pid):
            raise Exception()

    @classmethod
    def tearDownClass(cls):
        log.warn('teardown')
        try:
            os.kill(cls._pid, signal.SIGTERM)
        except:
            log.exception("Ignoring stuff")

    def test_write_file(self):
        name = 'test_write_file.txt'
        content = 'write test file content'
        share_path = os.path.join(self.public_dir, name)
        assert not os.path.exists(share_path)

        local_path = tempfile.mktemp()
        with open(local_path, 'w') as fp:
            fp.write(content)
        conn = salt.utils.smb.get_conn('127.0.0.1', self.username, 'foo', port=1445)
        salt.utils.smb.put_file(local_path, name, 'public', conn=conn)
        conn.close()

        with open(share_path, 'r') as fp:
            result = fp.read()
        assert result == content

    def test_delete_file(self):
        name = 'test_delete_file.txt'
        content = 'read test file content'
        share_path = os.path.join(self.public_dir, name)
        with open(share_path, 'w') as fp:
            fp.write(content)
        assert os.path.exists(share_path)

        conn = salt.utils.smb.get_conn('127.0.0.1', self.username, 'foo', port=1445)
        salt.utils.smb.delete_file(name, 'public', conn=conn)
        conn.close()

        assert not os.path.exists(share_path)

    def test_connection(self):
        conn = salt.utils.smb.get_conn('127.0.0.1', self.username, 'foo', port=1445)
        conn.close()
        time.sleep(.1)
