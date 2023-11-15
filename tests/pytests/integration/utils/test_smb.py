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
from pathlib import Path

import pytest
import saltfactories.utils.tempfiles

import salt.utils.files
import salt.utils.network
import salt.utils.path
import salt.utils.smb

log = logging.getLogger(__name__)

IPV6_ENABLED = bool(salt.utils.network.ip_addrs6(include_loopback=True))


pytestmark = [
    pytest.mark.skipif(
        not salt.utils.smb.HAS_SMBPROTOCOL,
        reason='"smbprotocol" needs to be installed.',
    ),
    pytest.mark.skip_if_binaries_missing("smbd", check_all=False),
    pytest.mark.skip_unless_on_linux(reason="using Linux samba to test smb"),
]


def check_pid(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


@pytest.fixture
def smb_dict():
    with saltfactories.utils.tempfiles.temp_directory() as tmpdir:
        samba_dir = Path(str(tmpdir) + os.sep + "samba")
        samba_dir.mkdir(parents=True)
        assert samba_dir.exists()
        assert samba_dir.is_dir()
        public_dir = Path(str(tmpdir) + os.sep + "public")
        public_dir.mkdir(parents=True)
        assert public_dir.exists()
        assert public_dir.is_dir()

        passwdb = Path(str(tmpdir) + os.sep + "passwdb")
        username = getpass.getuser()
        with salt.utils.files.fopen(passwdb, "w") as fp:
            fp.write(
                "{username}:0:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX:AC8E657F8"
                "3DF82BEEA5D43BDAF7800CC:[U          ]:LCT-507C14C7:"
            )

        samba_conf = Path(str(tmpdir) + os.sep + "smb.conf")
        with salt.utils.files.fopen(samba_conf, "w") as fp:
            fp.write(
                f"[global]\n"
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
                "force user = {username}\n"
            )
        _smbd = subprocess.Popen([shutil.which("smbd"), "-F", "-P0", "-s", samba_conf])
        time.sleep(1)

        conn_dict = {
            "tmpdir": tmpdir,
            "samba_dir": samba_dir,
            "public_dir": public_dir,
            "passwdb": passwdb,
            "username": username,
            "samba_conf": samba_conf,
        }

        pidfile = Path(str(samba_dir) + os.sep + "smbd.pid")
        assert pidfile.exists()
        with salt.utils.files.fopen(pidfile, "r") as fp:
            _pid = int(fp.read().strip())
        if not check_pid(_pid):
            raise Exception("Unable to locate smbd's pid file")

        yield conn_dict

        log.warning("teardown")
        os.kill(_pid, signal.SIGTERM)


def test_write_file_ipv4(smb_dict):
    """
    Transfer a file over SMB
    """
    name = "test_write_file_v4.txt"
    content = "write test file content ipv4"
    share_path = Path(str(smb_dict["public_dir"]) + os.sep + name)
    assert not share_path.exists()

    local_path = tempfile.mktemp()
    with salt.utils.files.fopen(local_path, "w") as fp:
        fp.write(content)
    conn = salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    salt.utils.smb.put_file(local_path, name, "public", conn=conn)
    conn.close()

    assert share_path.exists()
    with salt.utils.files.fopen(share_path, "r") as fp:
        result = fp.read()
    assert result == content


@pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
def test_write_file_ipv6(smb_dict):
    """
    Transfer a file over SMB
    """
    name = "test_write_file_v6.txt"
    content = "write test file content ipv6"
    share_path = Path(str(smb_dict["public_dir"]) + os.sep + name)
    assert not share_path.exists()

    local_path = tempfile.mktemp()
    with salt.utils.files.fopen(local_path, "w") as fp:
        fp.write(content)
    conn = salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    salt.utils.smb.put_file(local_path, name, "public", conn=conn)
    conn.close()

    assert share_path.exists()
    with salt.utils.files.fopen(share_path, "r") as fp:
        result = fp.read()
    assert result == content


def test_write_str_v4(smb_dict):
    """
    Write a string to a file over SMB
    """
    name = "test_write_str.txt"
    content = "write test file content"
    share_path = Path(str(smb_dict["public_dir"]) + os.sep + name)
    assert not share_path.exists()
    conn = salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    salt.utils.smb.put_str(content, name, "public", conn=conn)
    conn.close()

    assert share_path.exists()
    with salt.utils.files.fopen(share_path, "r") as fp:
        result = fp.read()
    assert result == content


@pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
def test_write_str_v6(smb_dict):
    """
    Write a string to a file over SMB
    """
    name = "test_write_str_v6.txt"
    content = "write test file content"
    share_path = Path(str(smb_dict["public_dir"]) + os.sep + name)
    assert not share_path.exists()
    conn = salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    salt.utils.smb.put_str(content, name, "public", conn=conn)
    conn.close()

    assert share_path.exists()
    with salt.utils.files.fopen(share_path, "r") as fp:
        result = fp.read()
    assert result == content


def test_delete_file_v4(smb_dict):
    """
    Validate deletion of files over SMB
    """
    name = "test_delete_file.txt"
    content = "read test file content"
    share_path = Path(str(smb_dict["public_dir"]) + os.sep + name)
    with salt.utils.files.fopen(share_path, "w") as fp:
        fp.write(content)
    assert share_path.exists()

    conn = salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    salt.utils.smb.delete_file(name, "public", conn=conn)
    conn.close()
    assert not share_path.exists()


@pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
def test_delete_file_v6(smb_dict):
    """
    Validate deletion of files over SMB
    """
    name = "test_delete_file_v6.txt"
    content = "read test file content"
    share_path = Path(str(smb_dict["public_dir"]) + os.sep + name)
    with salt.utils.files.fopen(share_path, "w") as fp:
        fp.write(content)
    assert share_path.exists()

    conn = salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    salt.utils.smb.delete_file(name, "public", conn=conn)
    conn.close()
    assert not share_path.exists()


def test_mkdirs_v4(smb_dict):
    """
    Create directories over SMB
    """
    dir_name = "mkdirs/test"
    share_path = Path(str(smb_dict["public_dir"]) + os.sep + dir_name)
    assert not share_path.exists()

    conn = salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    salt.utils.smb.mkdirs(dir_name, "public", conn=conn)
    conn.close()
    assert share_path.exists()


@pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
def test_mkdirs_v6(smb_dict):
    """
    Create directories over SMB
    """
    dir_name = "mkdirs/testv6"
    share_path = Path(str(smb_dict["public_dir"]) + os.sep + dir_name)
    assert not share_path.exists()

    conn = salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    salt.utils.smb.mkdirs(dir_name, "public", conn=conn)
    conn.close()
    assert share_path.exists()


def test_delete_dirs_v4(smb_dict):
    """
    Validate deletion of directoreies over SMB
    """
    dir_name = "deldirs"
    subdir_name = "deldirs/test"
    local_path = Path(str(smb_dict["public_dir"]) + os.sep + subdir_name)
    local_path.mkdir(parents=True)
    assert local_path.exists()
    assert local_path.is_dir()

    conn = salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    salt.utils.smb.delete_directory(subdir_name, "public", conn=conn)
    conn.close()

    conn = salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    salt.utils.smb.delete_directory(dir_name, "public", conn=conn)
    conn.close()
    assert not local_path.exists()
    assert not Path(str(smb_dict["public_dir"]) + os.sep + dir_name).exists()


@pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
def test_delete_dirs_v6(smb_dict):
    """
    Validate deletion of directoreies over SMB
    """
    dir_name = "deldirsv6"
    subdir_name = "deldirsv6/test"
    local_path = Path(str(smb_dict["public_dir"]) + os.sep + subdir_name)
    local_path.mkdir(parents=True)
    assert local_path.exists()
    assert local_path.is_dir()

    conn = salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    salt.utils.smb.delete_directory(subdir_name, "public", conn=conn)
    conn.close()

    conn = salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    salt.utils.smb.delete_directory(dir_name, "public", conn=conn)
    conn.close()
    assert not local_path.exists()
    assert not Path(str(smb_dict["public_dir"]) + os.sep + dir_name).exists()


def test_connection(smb_dict):
    """
    Validate creation of an SMB connection
    """
    conn = salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    conn.close()


@pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
def test_connection_v6(smb_dict):
    """
    Validate creation of an SMB connection
    """
    conn = salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    conn.close()
