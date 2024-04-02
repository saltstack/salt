"""
Test utility methods that communicate with SMB shares.
"""

import contextlib
import logging
import shutil
import subprocess

import attr
import pytest
from pytestshellutils.exceptions import FactoryFailure, FactoryNotStarted
from pytestshellutils.shell import Daemon, ProcessResult
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
    host = attr.ib()
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
        for name in ("cache", "lock", "state", "logs"):
            path = self.runtime_dir / name
            path.mkdir(mode=0o0755)
        self.config_file_path.write_text(
            f"[global]\n"
            "realm = saltstack.com\n"
            f"interfaces = lo {self.host}/8\n"
            f"smb ports = {self.listen_port}\n"
            "log level = 2\n"
            "map to guest = Bad User\n"
            "enable core files = no\n"
            "passdb backend = smbpasswd\n"
            f"smb passwd file = {self.passwdb_file_path}\n"
            f"log file = {self.runtime_dir / 'logs' / 'log.%m'}\n"
            f"lock directory = {self.runtime_dir / 'lock'}\n"
            f"state directory = {self.runtime_dir / 'state'}\n"
            f"cache directory = {self.runtime_dir / 'cache'}\n"
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
        cmdline = [
            shutil.which("pdbedit"),
            "--create",
            f"--configfile={self.config_file_path}",
            "-w",
            "-u",
            self.username,
            "-t",
        ]
        ret = subprocess.run(
            cmdline,
            input=f"{self.password}\n{self.password}\n",
            capture_output=True,
            shell=False,
            check=False,
            text=True,
        )
        result = ProcessResult(
            returncode=ret.returncode,
            stdout=ret.stdout,
            stderr=ret.stderr,
            cmdline=cmdline,
        )
        if ret.returncode != 0:
            log.warning(result)
            raise FactoryFailure(
                f"Failed to add user {self.username} to {self.passwdb_file_path}"
            )
        log.debug(result)

    def _check_config(self):
        cmdline = [shutil.which("testparm"), "-s", str(self.config_file_path)]
        ret = subprocess.run(
            cmdline,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
        )
        result = ProcessResult(
            returncode=ret.returncode,
            stdout=ret.stdout,
            stderr=ret.stderr,
            cmdline=cmdline,
        )
        if ret.returncode != 0:
            log.warning(result)
            raise FactoryFailure(f"""Failed to run '{" ".join(cmdline)}'""")
        log.debug(result)

    def __attrs_post_init__(self):
        """
        Post attrs initialization routines.
        """
        self.check_ports = [self.listen_port]
        super().__attrs_post_init__()
        self._write_config()
        self._create_account()
        self._check_config()

    def get_display_name(self):
        """
        Returns a human readable name for the factory.
        """
        if self.display_name is None:
            self.display_name = "{}(host={}, port={})".format(
                self.__class__.__name__, self.host, self.listen_port
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
                self.host, self.username, self.password, port=self.listen_port
            )
        ) as conn:
            yield conn


@pytest.fixture(scope="module", params=["127.0.0.1", "::0"], ids=["IPv4", "IPv6"])
def smbd_host(request):
    if request.param == "::0" and not IPV6_ENABLED:
        raise pytest.skip(reason="IPv6 not enabled")
    return request.param


@pytest.fixture(scope="module")
def smbd_factory(smbd_host, tmp_path_factory, salt_factories):
    runtime_dir = tmp_path_factory.mktemp("samba-runtime")
    smdb_kwargs = {
        "cwd": runtime_dir,
        "runtime_dir": runtime_dir,
        "start_timeout": 30,
        "host": smbd_host,
    }
    if salt_factories.stats_processes is not None:
        smdb_kwargs["stats_processes"] = salt_factories.stats_processes
    try:
        with Smbd(**smdb_kwargs).started() as daemon:
            yield daemon
    except FactoryNotStarted as exc:
        log.error("Factory failed to start. Spitting daemon logs...")
        for fpath in runtime_dir.joinpath("logs").glob("*"):
            log.warning(
                "Contents of '%s':\n>>>>>>>>>>>>>>>>>>\n%s\n<<<<<<<<<<<<<<<<<<\n",
                fpath,
                fpath.read_text(),
            )
        raise exc from None


@pytest.fixture
def smbd(smbd_factory):
    try:
        yield smbd_factory
    finally:
        shutil.rmtree(smbd_factory.public_dir, ignore_errors=True)
        smbd_factory.public_dir.mkdir()


def test_write_file(smbd, tmp_path):
    """
    Transfer a file over SMB
    """
    name = "test_write_file.txt"
    content = "write test file content"
    share_path = smbd.public_dir / name
    assert not share_path.exists()

    local_path = tmp_path / name
    local_path.write_text(content)

    with smbd.get_conn() as conn:
        salt.utils.smb.put_file(local_path, name, "public", conn=conn)

    assert share_path.exists()
    result = share_path.read_text()
    assert result == content


def test_write_str(smbd):
    """
    Write a string to a file over SMB
    """
    name = "test_write_str.txt"
    content = "write test file content"
    share_path = smbd.public_dir / name
    assert not share_path.exists()

    with smbd.get_conn() as conn:
        salt.utils.smb.put_str(content, name, "public", conn=conn)

    assert share_path.exists()
    result = share_path.read_text()
    assert result == content


def test_delete_file_v4(smbd):
    """
    Validate deletion of files over SMB
    """
    name = "test_delete_file.txt"
    content = "read test file content"
    share_path = smbd.public_dir / name
    assert not share_path.exists()
    share_path.write_text(content)
    assert share_path.exists()

    with smbd.get_conn() as conn:
        salt.utils.smb.delete_file(name, "public", conn=conn)

    assert not share_path.exists()


def test_mkdirs(smbd):
    """
    Create directories over SMB
    """
    dir_name = "subdir/test"
    share_path = smbd.public_dir / dir_name
    assert not share_path.exists()

    with smbd.get_conn() as conn:
        salt.utils.smb.mkdirs(dir_name, "public", conn=conn)

    assert share_path.exists()


def test_delete_dirs(smbd):
    """
    Validate deletion of directoreies over SMB
    """
    subdir_name = "subdir"
    dir_name = f"{subdir_name}/test"
    share_path = smbd.public_dir / dir_name
    share_path.mkdir(parents=True)

    with smbd.get_conn() as conn:
        salt.utils.smb.delete_directory(dir_name, "public", conn=conn)

    assert share_path.is_dir() is False

    with smbd.get_conn() as conn:
        salt.utils.smb.delete_directory(subdir_name, "public", conn=conn)

    assert share_path.parent.is_dir() is False
