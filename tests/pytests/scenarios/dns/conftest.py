import logging
import pathlib
import subprocess

import pytest

from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)


@pytest.fixture(scope="package")
def master_alive_interval():
    return 5


class HostsFile:
    """
    Simple helper class for tests that need to modify /etc/hosts.
    """

    def __init__(self, path, orig_text):
        self._path = path
        self._orig_text = orig_text

    @property
    def orig_text(self):
        return self._orig_text

    def __getattr__(self, key):
        if key in ["_path", "_orig_text", "orig_text"]:
            return self.__getattribute__(key)
        return getattr(self._path, key)


@pytest.fixture
def etc_hosts():
    hosts = pathlib.Path("/etc/hosts")
    orig_text = hosts.read_text(encoding="utf-8")
    hosts = HostsFile(hosts, orig_text)
    try:
        yield hosts
    finally:
        hosts.write_text(orig_text)


@pytest.fixture(scope="package")
def master(request, salt_factories):

    subprocess.check_output(["ip", "addr", "add", "172.16.0.1/32", "dev", "lo"])

    config_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = {
        "interface": "0.0.0.0",
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        "master",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=180):
        yield factory

    try:
        subprocess.check_output(["ip", "addr", "del", "172.16.0.1/32", "dev", "lo"])
    except subprocess.CalledProcessError:
        pass


@pytest.fixture(scope="package")
def salt_cli(master):
    return master.salt_cli(timeout=180)


@pytest.fixture(scope="package")
def minion(master, master_alive_interval):
    config_defaults = {
        "transport": master.config["transport"],
    }
    port = master.config["ret_port"]
    config_overrides = {
        "master": f"master.local:{port}",
        "publish_port": master.config["publish_port"],
        "master_alive_interval": master_alive_interval,
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = master.salt_minion_daemon(
        "minion",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    return factory
