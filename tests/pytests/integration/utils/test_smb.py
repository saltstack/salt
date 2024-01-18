"""
Test utility methods that communicate with SMB shares.
"""
import contextlib
import logging
import shutil
import subprocess

import attr
import pytest
from pytestshellutils.exceptions import FactoryFailure
from pytestshellutils.shell import Daemon
from pytestshellutils.utils import ports
from saltfactories.utils import random_string, running_username

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
    pytest.mark.skip_if_binaries_missing("smbd", "pdbedit"),
    pytest.mark.skip_unless_on_linux,
]


@attr.s(kw_only=True, slots=True)
class Smbd(Daemon):
    """
    SSHD implementation.
    """

    runtime_dir = attr.ib()
    script_name = attr.ib(default=shutil.which("smbd"))
    display_name = attr.ib(default=None)
    listen_port = attr.ib(factory=ports.get_unused_localhost_port)
    username = attr.ib(init=False, factory=running_username)
    password = attr.ib(init=False, repr=False)
    public_dir = attr.ib(init=False, repr=False)
    config_dir = attr.ib(init=False, repr=False)
    passwdb_file_path = attr.ib(init=False, repr=False)
    config_file_path = attr.ib(init=False, repr=False)

    @password.default
    def _default_password(self):
        return random_string(f"{self.username}-")

    @config_dir.default
    def _default_config_dir(self):
        path = self.runtime_dir / "conf"
        path.mkdir()
        return path

    @public_dir.default
    def _default_public_dir(self):
        path = self.runtime_dir / "public"
        path.mkdir()
        return path

    @passwdb_file_path.default
    def _default_passwdb_path(self):
        return self.config_dir / "passwdb"

    @config_file_path.default
    def _default_config_file_path(self):
        return self.config_dir / "smb.conf"

    def _write_config(self):
        self.config_file_path.write_text(
            f"[global]\n"
            "realm = saltstack.com\n"
            "interfaces = lo 127.0.0.0/8\n"
            f"smb ports = {self.listen_port}\n"
            "log level = 2\n"
            "map to guest = Bad User\n"
            "enable core files = no\n"
            "passdb backend = smbpasswd\n"
            f"smb passwd file = {self.passwdb_file_path}\n"
            f"log file = {self.runtime_dir / 'log.%m'}\n"
            f"lock directory = {self.runtime_dir}\n"
            f"state directory = {self.runtime_dir}\n"
            f"cache directory = {self.runtime_dir}\n"
            f"pid directory = {self.runtime_dir}\n"
            f"private dir = {self.runtime_dir}\n"
            f"ncalrpc dir = {self.runtime_dir}\n"
            "socket options = IPTOS_LOWDELAY TCP_NODELAY\n"
            "min receivefile size = 0\n"
            "write cache size = 0\n"
            "client ntlmv2 auth = no\n"
            "client min protocol = SMB3_11\n"
            "client plaintext auth = no\n"
            "\n"
            "[public]\n"
            f"path = {self.public_dir}\n"
            "read only = no\n"
            "guest ok = no\n"
            "writeable = yes\n"
            f"force user = {self.username}\n"
        )

    def _create_account(self):
        ret = subprocess.run(
            [
                shutil.which("pdbedit"),
                "--create",
                f"--configfile={self.config_file_path}",
                "-w",
                "-u",
                self.username,
                "-t",
            ],
            input=f"{self.password}\n{self.password}\n".encode(),
            shell=False,
            check=False,
        )
        if ret.returncode != 0:
            raise FactoryFailure(
                f"Failed to add user {self.username} to {self.passwdb_file_path}"
            )

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        self.check_ports = [self.listen_port]
        super().__attrs_post_init__()
        self._write_config()
        self._create_account()

    def get_display_name(self):
        """
        Returns a human readable name for the factory.
        """
        if self.display_name is None:
            self.display_name = "{}(port={})".format(
                self.__class__.__name__, self.listen_port
            )
        return super().get_display_name()

    def get_base_script_args(self):
        """
        Returns any additional arguments to pass to the CLI script.
        """
        return [
            "--foreground",
            f"--configfile={self.config_file_path}",
        ]

    @contextlib.contextmanager
    def get_conn(self):
        with contextlib.closing(
            salt.utils.smb.get_conn(
                "127.0.0.1", self.username, self.password, port=self.listen_port
            )
        ) as conn:
            yield conn


@pytest.fixture(scope="module")
def smbd(tmp_path_factory):
    runtime_dir = tmp_path_factory.mktemp("samba-runtime")
    daemon = Smbd(runtime_dir=runtime_dir, cwd=runtime_dir, start_timeout=30)
    with daemon.started():
        yield daemon


def test_write_file_ipv4(smbd, tmp_path):
    """
    Transfer a file over SMB
    """
    name = "test_write_file_v4.txt"
    content = "write test file content ipv4"
    share_path = smbd.public_dir / name
    assert not share_path.exists()

    local_path = tmp_path / name
    local_path.write_text(content)

    with smbd.get_conn() as conn:
        salt.utils.smb.put_file(local_path, name, "public", conn=conn)

    assert share_path.exists()
    result = share_path.read_text()
    assert result == content


## DGM
## DGM @pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
## DGM def test_write_file_ipv6(smb_dict):
## DGM     """
## DGM     Transfer a file over SMB
## DGM     """
## DGM     name = "test_write_file_v6.txt"
## DGM     content = "write test file content ipv6"
## DGM     share_path = smb_dict["public_dir"] / name
## DGM     assert not share_path.exists()
## DGM
## DGM     local_path = tempfile.mktemp()
## DGM     with salt.utils.files.fopen(local_path, "w") as fp:
## DGM         fp.write(content)
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         salt.utils.smb.put_file(local_path, name, "public", conn=conn)
## DGM
## DGM     assert share_path.exists()
## DGM     with salt.utils.files.fopen(share_path, "r") as fp:
## DGM         result = fp.read()
## DGM     assert result == content
## DGM
## DGM
## DGM def test_write_str_v4(smb_dict):
## DGM     """
## DGM     Write a string to a file over SMB
## DGM     """
## DGM     name = "test_write_str.txt"
## DGM     content = "write test file content"
## DGM     share_path = smb_dict["public_dir"] / name
## DGM     assert not share_path.exists()
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         salt.utils.smb.put_str(content, name, "public", conn=conn)
## DGM
## DGM     assert share_path.exists()
## DGM     with salt.utils.files.fopen(share_path, "r") as fp:
## DGM         result = fp.read()
## DGM     assert result == content
## DGM
## DGM
## DGM @pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
## DGM def test_write_str_v6(smb_dict):
## DGM     """
## DGM     Write a string to a file over SMB
## DGM     """
## DGM     name = "test_write_str_v6.txt"
## DGM     content = "write test file content"
## DGM     share_path = smb_dict["public_dir"] / name
## DGM     assert not share_path.exists()
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         salt.utils.smb.put_str(content, name, "public", conn=conn)
## DGM
## DGM     assert share_path.exists()
## DGM     with salt.utils.files.fopen(share_path, "r") as fp:
## DGM         result = fp.read()
## DGM     assert result == content
## DGM
## DGM
## DGM def test_delete_file_v4(smb_dict):
## DGM     """
## DGM     Validate deletion of files over SMB
## DGM     """
## DGM     name = "test_delete_file.txt"
## DGM     content = "read test file content"
## DGM     share_path = smb_dict["public_dir"] / name
## DGM     with salt.utils.files.fopen(share_path, "w") as fp:
## DGM         fp.write(content)
## DGM     assert share_path.exists()
## DGM
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         salt.utils.smb.delete_file(name, "public", conn=conn)
## DGM
## DGM     assert not share_path.exists()
## DGM
## DGM
## DGM @pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
## DGM def test_delete_file_v6(smb_dict):
## DGM     """
## DGM     Validate deletion of files over SMB
## DGM     """
## DGM     name = "test_delete_file_v6.txt"
## DGM     content = "read test file content"
## DGM     share_path = smb_dict["public_dir"] / name
## DGM     with salt.utils.files.fopen(share_path, "w") as fp:
## DGM         fp.write(content)
## DGM     assert share_path.exists()
## DGM
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         salt.utils.smb.delete_file(name, "public", conn=conn)
## DGM
## DGM     assert not share_path.exists()
## DGM
## DGM
## DGM def test_mkdirs_v4(smb_dict):
## DGM     """
## DGM     Create directories over SMB
## DGM     """
## DGM     dir_name = "mkdirs/test"
## DGM     share_path = smb_dict["public_dir"] / dir_name
## DGM     assert not share_path.exists()
## DGM
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         salt.utils.smb.mkdirs(dir_name, "public", conn=conn)
## DGM
## DGM     assert share_path.exists()
## DGM
## DGM
## DGM @pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
## DGM def test_mkdirs_v6(smb_dict):
## DGM     """
## DGM     Create directories over SMB
## DGM     """
## DGM     dir_name = "mkdirs/testv6"
## DGM     share_path = smb_dict["public_dir"] / dir_name
## DGM     assert not share_path.exists()
## DGM
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         salt.utils.smb.mkdirs(dir_name, "public", conn=conn)
## DGM
## DGM     assert share_path.exists()
## DGM
## DGM
## DGM def test_delete_dirs_v4(smb_dict):
## DGM     """
## DGM     Validate deletion of directoreies over SMB
## DGM     """
## DGM     dir_name = "deldirs"
## DGM     subdir_name = "deldirs/test"
## DGM     local_path = smb_dict["public_dir"] / subdir_name
## DGM     local_path.mkdir(parents=True)
## DGM     assert local_path.exists()
## DGM     assert local_path.is_dir()
## DGM
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         salt.utils.smb.delete_directory(subdir_name, "public", conn=conn)
## DGM
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         salt.utils.smb.delete_directory(dir_name, "public", conn=conn)
## DGM
## DGM     assert not local_path.exists()
## DGM     assert not (smb_dict["public_dir"] / dir_name).exists()
## DGM
## DGM
## DGM @pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
## DGM def test_delete_dirs_v6(smb_dict):
## DGM     """
## DGM     Validate deletion of directoreies over SMB
## DGM     """
## DGM     dir_name = "deldirsv6"
## DGM     subdir_name = "deldirsv6/test"
## DGM     local_path = smb_dict["public_dir"] / subdir_name
## DGM     local_path.mkdir(parents=True)
## DGM     assert local_path.exists()
## DGM     assert local_path.is_dir()
## DGM
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         salt.utils.smb.delete_directory(subdir_name, "public", conn=conn)
## DGM
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         salt.utils.smb.delete_directory(dir_name, "public", conn=conn)
## DGM
## DGM     assert not local_path.exists()
## DGM     assert not (smb_dict["public_dir"] / dir_name).exists()
## DGM
## DGM
## DGM def test_connection(smb_dict):
## DGM     """
## DGM     Validate creation of an SMB connection
## DGM     """
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         pass
## DGM
## DGM
## DGM @pytest.mark.skipif(not IPV6_ENABLED, reason="IPv6 not enabled")
## DGM def test_connection_v6(smb_dict):
## DGM     """
## DGM     Validate creation of an SMB connection
## DGM     """
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("::1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         pass
## DGM
## DGM     with contextlib.closing(
## DGM         salt.utils.smb.get_conn("127.0.0.1", smb_dict["username"], "foo", port=1445)
## DGM     ) as conn:
## DGM         pass
