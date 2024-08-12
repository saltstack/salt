import logging
import subprocess

import pytest

import salt.utils.platform
from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)


@pytest.fixture
def cluster_shared_path(tmp_path):
    path = tmp_path / "cluster"
    path.mkdir()
    return path


@pytest.fixture
def cluster_pki_path(cluster_shared_path):
    path = cluster_shared_path / "pki"
    path.mkdir()
    (path / "peers").mkdir()
    return path


@pytest.fixture
def cluster_cache_path(cluster_shared_path):
    path = cluster_shared_path / "cache"
    path.mkdir()
    return path


@pytest.fixture
def cluster_master_1(request, salt_factories, cluster_pki_path, cluster_cache_path):
    config_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = {
        "interface": "127.0.0.1",
        "cluster_id": "master_cluster",
        "cluster_peers": [
            "127.0.0.2",
            "127.0.0.3",
        ],
        "cluster_pki_dir": str(cluster_pki_path),
        "cache_dir": str(cluster_cache_path),
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
            "salt.utils.event": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }
    factory = salt_factories.salt_master_daemon(
        "127.0.0.1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def cluster_master_2(salt_factories, cluster_master_1):
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.2", "up"])

    config_defaults = {
        "open_mode": True,
        "transport": cluster_master_1.config["transport"],
    }
    config_overrides = {
        "interface": "127.0.0.2",
        "cluster_id": "master_cluster",
        "cluster_peers": [
            "127.0.0.1",
            "127.0.0.3",
        ],
        "cluster_pki_dir": cluster_master_1.config["cluster_pki_dir"],
        "cache_dir": cluster_master_1.config["cache_dir"],
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
            "salt.utils.event": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }

    # Use the same ports for both masters, they are binding to different interfaces
    for key in (
        "ret_port",
        "publish_port",
    ):
        config_overrides[key] = cluster_master_1.config[key]
    factory = salt_factories.salt_master_daemon(
        "127.0.0.2",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def cluster_master_3(salt_factories, cluster_master_1):
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.3", "up"])

    config_defaults = {
        "open_mode": True,
        "transport": cluster_master_1.config["transport"],
    }
    config_overrides = {
        "interface": "127.0.0.3",
        "cluster_id": "master_cluster",
        "cluster_peers": [
            "127.0.0.1",
            "127.0.0.2",
        ],
        "cluster_pki_dir": cluster_master_1.config["cluster_pki_dir"],
        "cache_dir": cluster_master_1.config["cache_dir"],
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
            "salt.utils.event": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
    }

    # Use the same ports for both masters, they are binding to different interfaces
    for key in (
        "ret_port",
        "publish_port",
    ):
        config_overrides[key] = cluster_master_1.config[key]
    factory = salt_factories.salt_master_daemon(
        "127.0.0.3",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def cluster_minion_1(cluster_master_1):
    config_defaults = {
        "transport": cluster_master_1.config["transport"],
    }

    port = cluster_master_1.config["ret_port"]
    addr = cluster_master_1.config["interface"]
    config_overrides = {
        "master": f"{addr}:{port}",
        "test.foo": "baz",
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
            "salt.utils.event": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = cluster_master_1.salt_minion_daemon(
        "cluster-minion-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory
