"""
Test utility methods that communicate with SMB shares.
"""
import contextlib
import getpass
import logging
import os
import pathlib
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

IPV6_ENABLED = bool(salt.utils.network.ip_addrs6(include_loopback=True))

log = logging.getLogger(__name__)

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
def smb_dict(tmp_path):
    samba_dir = tmp_path / "samba"
    samba_dir.mkdir(parents=True)
    assert samba_dir.exists()
    assert samba_dir.is_dir()
    public_dir = tmp_path / "public"
    public_dir.mkdir(parents=True)
    assert public_dir.exists()
    assert public_dir.is_dir()
    passwdb = tmp_path / "passwdb"
    username = getpass.getuser()
    with salt.utils.files.fopen(passwdb, "w") as fp:
        fp.write(
            f"{username}:0:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX:AC8E657F8"
            "3DF82BEEA5D43BDAF7800CC:[U          ]:LCT-507C14C7:"
        )
    samba_conf = tmp_path / "smb.conf"
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
            f"smb passwd file = {passwdb}\n"
            f"lock directory = {samba_dir}\n"
            f"state directory = {samba_dir}\n"
            f"cache directory = {samba_dir}\n"
            f"pid directory = {samba_dir}\n"
            f"private dir = {samba_dir}\n"
            f"ncalrpc dir = {samba_dir}\n"
            "socket options = IPTOS_LOWDELAY TCP_NODELAY\n"
            "min receivefile size = 0\n"
            "write cache size = 0\n"
            "client ntlmv2 auth = no\n"
            "client min protocol = SMB3_11\n"
            "client plaintext auth = no\n"
            "\n"
            "[public]\n"
            f"path = {public_dir}\n"
            "read only = no\n"
            "guest ok = no\n"
            "writeable = yes\n"
            f"force user = {username}\n"
        )

    ## _smbd = subprocess.Popen([shutil.which("smbd"), "-F", "-P0", "-s", samba_conf])
    ## _smbd = subprocess.Popen([smbd_path, "-F", "-P0", "-s", samba_conf])
    ## time.sleep(2)
    ## pidfile = samba_dir / "smbd.pid"
    ## conn_dict = {
    ##     "tmpdir": tmp_path,
    ##     "samba_dir": samba_dir,
    ##     "public_dir": public_dir,
    ##     "passwdb": passwdb,
    ##     "username": username,
    ##     "samba_conf": samba_conf,
    ##     "smbd_path": smbd_path,
    ##     "pidfile": pidfile,
    ## }

    ## assert pidfile.exists()

    smbd_path = shutil.which("smbd")
    pathlib.Path(smbd_path).exists()
    try:
        _smbd = subprocess.Popen(
            [smbd_path, "-i", "-d", "2", "-F", "-P0", "-s", samba_conf]
        )
        assert _smbd != 0
        time.sleep(2)
        pidfile = samba_dir / "smbd.pid"
        conn_dict = {
            "tmpdir": tmp_path,
            "samba_dir": samba_dir,
            "public_dir": public_dir,
            "passwdb": passwdb,
            "username": username,
            "samba_conf": samba_conf,
            "smbd_path": smbd_path,
            "pidfile": pidfile,
        }

        ## lets examine contents of samba_dir ditectory
        for file_dgm in pathlib.Path(samba_dir).iterdir():
            log.warning(f"DGM walking samba_dir, file '{file_dgm}'")
            if os.path.basename(str(file_dgm)) == "smbd.pid":
                log.warning(f"DGM walking samba_dir found smbd.pid, file '{file_dgm}'")
                assert "1" == "2"

        assert pidfile.exists()

    except (OSError, ValueError) as e:
        assert f"exception occured, '{e}'" == ""

    with salt.utils.files.fopen(pidfile, "r") as fp:
        _pid = int(fp.read().strip())
    if not check_pid(_pid):
        raise Exception("Unable to locate smbd's pid file")
    try:
        yield conn_dict
    finally:
        os.kill(_pid, signal.SIGTERM)


def test_write_file_ipv4(smb_dict):
    """
    Transfer a file over SMB
    """
    name = "test_write_file_v4.txt"
    content = "write test file content ipv4"
    share_path = smb_dict["public_dir"] / name
    assert not share_path.exists()

    local_path = tempfile.mktemp()
    with salt.utils.files.fopen(local_path, "w") as fp:
        fp.write(content)

    with contextlib.closing(
        salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        salt.utils.smb.put_file(local_path, name, "public", conn=conn)

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
    share_path = smb_dict["public_dir"] / name
    assert not share_path.exists()

    local_path = tempfile.mktemp()
    with salt.utils.files.fopen(local_path, "w") as fp:
        fp.write(content)
    with contextlib.closing(
        salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        salt.utils.smb.put_file(local_path, name, "public", conn=conn)

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
    share_path = smb_dict["public_dir"] / name
    assert not share_path.exists()
    with contextlib.closing(
        salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        salt.utils.smb.put_str(content, name, "public", conn=conn)

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
    share_path = smb_dict["public_dir"] / name
    assert not share_path.exists()
    with contextlib.closing(
        salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        salt.utils.smb.put_str(content, name, "public", conn=conn)

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
    share_path = smb_dict["public_dir"] / name
    with salt.utils.files.fopen(share_path, "w") as fp:
        fp.write(content)
    assert share_path.exists()

    with contextlib.closing(
        salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        salt.utils.smb.delete_file(name, "public", conn=conn)

    assert not share_path.exists()


@pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
def test_delete_file_v6(smb_dict):
    """
    Validate deletion of files over SMB
    """
    name = "test_delete_file_v6.txt"
    content = "read test file content"
    share_path = smb_dict["public_dir"] / name
    with salt.utils.files.fopen(share_path, "w") as fp:
        fp.write(content)
    assert share_path.exists()

    with contextlib.closing(
        salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        salt.utils.smb.delete_file(name, "public", conn=conn)

    assert not share_path.exists()


def test_mkdirs_v4(smb_dict):
    """
    Create directories over SMB
    """
    dir_name = "mkdirs/test"
    share_path = smb_dict["public_dir"] / dir_name
    assert not share_path.exists()

    with contextlib.closing(
        salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        salt.utils.smb.mkdirs(dir_name, "public", conn=conn)

    assert share_path.exists()


@pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
def test_mkdirs_v6(smb_dict):
    """
    Create directories over SMB
    """
    dir_name = "mkdirs/testv6"
    share_path = smb_dict["public_dir"] / dir_name
    assert not share_path.exists()

    with contextlib.closing(
        salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        salt.utils.smb.mkdirs(dir_name, "public", conn=conn)

    assert share_path.exists()


def test_delete_dirs_v4(smb_dict):
    """
    Validate deletion of directoreies over SMB
    """
    dir_name = "deldirs"
    subdir_name = "deldirs/test"
    local_path = smb_dict["public_dir"] / subdir_name
    local_path.mkdir(parents=True)
    assert local_path.exists()
    assert local_path.is_dir()

    with contextlib.closing(
        salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        salt.utils.smb.delete_directory(subdir_name, "public", conn=conn)

    with contextlib.closing(
        salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        salt.utils.smb.delete_directory(dir_name, "public", conn=conn)

    assert not local_path.exists()
    assert not (smb_dict["public_dir"] / dir_name).exists()


@pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
def test_delete_dirs_v6(smb_dict):
    """
    Validate deletion of directoreies over SMB
    """
    dir_name = "deldirsv6"
    subdir_name = "deldirsv6/test"
    local_path = smb_dict["public_dir"] / subdir_name
    local_path.mkdir(parents=True)
    assert local_path.exists()
    assert local_path.is_dir()

    with contextlib.closing(
        salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        salt.utils.smb.delete_directory(subdir_name, "public", conn=conn)

    with contextlib.closing(
        salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        salt.utils.smb.delete_directory(dir_name, "public", conn=conn)

    assert not local_path.exists()
    assert not (smb_dict["public_dir"] / dir_name).exists()


def test_connection(smb_dict):
    """
    Validate creation of an SMB connection
    """
    with contextlib.closing(
        salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        pass


@pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
def test_connection_v6(smb_dict):
    """
    Validate creation of an SMB connection
    """
    with contextlib.closing(
        salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        pass

    with contextlib.closing(
        salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
    ) as conn:
        pass
