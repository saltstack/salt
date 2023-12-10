"""
Test utility methods that communicate with SMB shares.
"""
import getpass
import logging
import os
import shutil
import signal
import subprocess
import tempfile
import time

import pytest

import salt.utils.files
import salt.utils.network
import salt.utils.path
import salt.utils.smb
from tests.support.case import TestCase

log = logging.getLogger(__name__)
CONFIG = (
    "[global]\n"
    "realm = saltstack.com\n"
    "interfaces = lo 127.0.0.0/8\n"
    "smb ports = 1445\n"
    "log level = 2\n"
    "map to guest = Bad User\n"
    "enable core files = no\n"
    "passdb backend = smbpasswd\n"
    "smb passwd file = {passwdb}\n"
    "lock directory = {samba_dir}\n"
    "state directory = {samba_dir}\n"
    "cache directory = {samba_dir}\n"
    "pid directory = {samba_dir}\n"
    "private dir = {samba_dir}\n"
    "ncalrpc dir = {samba_dir}\n"
    "socket options = IPTOS_LOWDELAY TCP_NODELAY\n"
    "min receivefile size = 0\n"
    "write cache size = 0\n"
    "client ntlmv2 auth = no\n"
    "client min protocol = SMB3_11\n"
    "client plaintext auth = no\n"
    "\n"
    "[public]\n"
    "path = {public_dir}\n"
    "read only = no\n"
    "guest ok = no\n"
    "writeable = yes\n"
    "force user = {user}\n"
)
TBE = (
    "{}:0:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX:AC8E657F8"
    "3DF82BEEA5D43BDAF7800CC:[U          ]:LCT-507C14C7:"
)
IPV6_ENABLED = bool(salt.utils.network.ip_addrs6(include_loopback=True))


@pytest.mark.skipif(
    not salt.utils.smb.HAS_SMBPROTOCOL, reason='"smbprotocol" needs to be installed.'
)
@pytest.mark.skip_if_binaries_missing("smbd")
class TestSmb(TestCase):

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
        cls.samba_dir = os.path.join(tmpdir, "samba")
        cls.public_dir = os.path.join(tmpdir, "public")
        os.makedirs(cls.samba_dir)
        os.makedirs(cls.public_dir)
        os.chmod(cls.samba_dir, 0o775)
        os.chmod(cls.public_dir, 0o775)
        passwdb = os.path.join(tmpdir, "passwdb")
        cls.username = getpass.getuser()
        with salt.utils.files.fopen(passwdb, "w") as fp:
            fp.write(TBE.format(cls.username))
        samba_conf = os.path.join(tmpdir, "smb.conf")
        with salt.utils.files.fopen(samba_conf, "w") as fp:
            fp.write(
                CONFIG.format(
                    samba_dir=cls.samba_dir,
                    public_dir=cls.public_dir,
                    passwdb=passwdb,
                    user=cls.username,
                )
            )
        cls._smbd = subprocess.Popen(
            [shutil.which("smbd"), "-FS", "-P0", "-s", samba_conf]
        )
        time.sleep(1)
        pidfile = os.path.join(cls.samba_dir, "smbd.pid")
        with salt.utils.files.fopen(pidfile, "r") as fp:
            cls._pid = int(fp.read().strip())
        if not cls.check_pid(cls._pid):
            raise Exception("Unable to locate smbd's pid file")

    @classmethod
    def tearDownClass(cls):
        log.warning("teardown")
        os.kill(cls._pid, signal.SIGTERM)

    def test_write_file_ipv4(self):
        """
        Transfer a file over SMB
        """
        name = "test_write_file_v4.txt"
        content = "write test file content ipv4"
        share_path = os.path.join(self.public_dir, name)
        assert not os.path.exists(share_path)

        local_path = tempfile.mktemp()
        with salt.utils.files.fopen(local_path, "w") as fp:
            fp.write(content)
        conn = salt.utils.smb.get_conn("127.0.0.1", self.username, "foo", port=1445)
        salt.utils.smb.put_file(local_path, name, "public", conn=conn)
        conn.close()

        assert os.path.exists(share_path)
        with salt.utils.files.fopen(share_path, "r") as fp:
            result = fp.read()
        assert result == content

    @pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
    def test_write_file_ipv6(self):
        """
        Transfer a file over SMB
        """
        name = "test_write_file_v6.txt"
        content = "write test file content ipv6"
        share_path = os.path.join(self.public_dir, name)
        assert not os.path.exists(share_path)

        local_path = tempfile.mktemp()
        with salt.utils.files.fopen(local_path, "w") as fp:
            fp.write(content)
        conn = salt.utils.smb.get_conn("::1", self.username, "foo", port=1445)
        salt.utils.smb.put_file(local_path, name, "public", conn=conn)
        conn.close()

        assert os.path.exists(share_path)
        with salt.utils.files.fopen(share_path, "r") as fp:
            result = fp.read()
        assert result == content

    def test_write_str_v4(self):
        """
        Write a string to a file over SMB
        """
        name = "test_write_str.txt"
        content = "write test file content"
        share_path = os.path.join(self.public_dir, name)
        assert not os.path.exists(share_path)
        conn = salt.utils.smb.get_conn("127.0.0.1", self.username, "foo", port=1445)
        salt.utils.smb.put_str(content, name, "public", conn=conn)
        conn.close()

        assert os.path.exists(share_path)
        with salt.utils.files.fopen(share_path, "r") as fp:
            result = fp.read()
        assert result == content

    @pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
    def test_write_str_v6(self):
        """
        Write a string to a file over SMB
        """
        name = "test_write_str_v6.txt"
        content = "write test file content"
        share_path = os.path.join(self.public_dir, name)
        assert not os.path.exists(share_path)
        conn = salt.utils.smb.get_conn("::1", self.username, "foo", port=1445)
        salt.utils.smb.put_str(content, name, "public", conn=conn)
        conn.close()

        assert os.path.exists(share_path)
        with salt.utils.files.fopen(share_path, "r") as fp:
            result = fp.read()
        assert result == content

    def test_delete_file_v4(self):
        """
        Validate deletion of files over SMB
        """
        name = "test_delete_file.txt"
        content = "read test file content"
        share_path = os.path.join(self.public_dir, name)
        with salt.utils.files.fopen(share_path, "w") as fp:
            fp.write(content)
        assert os.path.exists(share_path)

        conn = salt.utils.smb.get_conn("127.0.0.1", self.username, "foo", port=1445)
        salt.utils.smb.delete_file(name, "public", conn=conn)
        conn.close()

        assert not os.path.exists(share_path)

    @pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
    def test_delete_file_v6(self):
        """
        Validate deletion of files over SMB
        """
        name = "test_delete_file_v6.txt"
        content = "read test file content"
        share_path = os.path.join(self.public_dir, name)
        with salt.utils.files.fopen(share_path, "w") as fp:
            fp.write(content)
        assert os.path.exists(share_path)

        conn = salt.utils.smb.get_conn("::1", self.username, "foo", port=1445)
        salt.utils.smb.delete_file(name, "public", conn=conn)
        conn.close()

        assert not os.path.exists(share_path)

    def test_mkdirs_v4(self):
        """
        Create directories over SMB
        """
        dir_name = "mkdirs/test"
        share_path = os.path.join(self.public_dir, dir_name)
        assert not os.path.exists(share_path)

        conn = salt.utils.smb.get_conn("127.0.0.1", self.username, "foo", port=1445)
        salt.utils.smb.mkdirs(dir_name, "public", conn=conn)
        conn.close()

        assert os.path.exists(share_path)

    @pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
    def test_mkdirs_v6(self):
        """
        Create directories over SMB
        """
        dir_name = "mkdirs/testv6"
        share_path = os.path.join(self.public_dir, dir_name)
        assert not os.path.exists(share_path)

        conn = salt.utils.smb.get_conn("::1", self.username, "foo", port=1445)
        salt.utils.smb.mkdirs(dir_name, "public", conn=conn)
        conn.close()

        assert os.path.exists(share_path)

    def test_delete_dirs_v4(self):
        """
        Validate deletion of directoreies over SMB
        """
        dir_name = "deldirs"
        subdir_name = "deldirs/test"
        local_path = os.path.join(self.public_dir, subdir_name)
        os.makedirs(local_path)
        assert os.path.exists(local_path)

        conn = salt.utils.smb.get_conn("127.0.0.1", self.username, "foo", port=1445)
        salt.utils.smb.delete_directory(subdir_name, "public", conn=conn)
        conn.close()

        conn = salt.utils.smb.get_conn("127.0.0.1", self.username, "foo", port=1445)
        salt.utils.smb.delete_directory(dir_name, "public", conn=conn)
        conn.close()

        assert not os.path.exists(local_path)
        assert not os.path.exists(os.path.join(self.public_dir, dir_name))

    @pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
    def test_delete_dirs_v6(self):
        """
        Validate deletion of directoreies over SMB
        """
        dir_name = "deldirsv6"
        subdir_name = "deldirsv6/test"
        local_path = os.path.join(self.public_dir, subdir_name)
        os.makedirs(local_path)
        assert os.path.exists(local_path)

        conn = salt.utils.smb.get_conn("::1", self.username, "foo", port=1445)
        salt.utils.smb.delete_directory(subdir_name, "public", conn=conn)
        conn.close()

        conn = salt.utils.smb.get_conn("::1", self.username, "foo", port=1445)
        salt.utils.smb.delete_directory(dir_name, "public", conn=conn)
        conn.close()

        assert not os.path.exists(local_path)
        assert not os.path.exists(os.path.join(self.public_dir, dir_name))

    def test_connection(self):
        """
        Validate creation of an SMB connection
        """
        conn = salt.utils.smb.get_conn("127.0.0.1", self.username, "foo", port=1445)
        conn.close()

    @pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
    def test_connection_v6(self):
        """
        Validate creation of an SMB connection
        """
        conn = salt.utils.smb.get_conn("::1", self.username, "foo", port=1445)
        conn.close()
