import logging
import subprocess

import pytest

import salt.utils.platform

# pylint: disable=unused-import
from tests.conftest import FIPS_TESTRUN
from tests.pytests.integration.cluster.conftest import (
    _isolated_master_overrides,
    cluster_cache_path,
    cluster_cache_path_isolated,
    cluster_file_roots_path_isolated,
    cluster_master_1,
    cluster_master_1_isolated,
    cluster_master_2,
    cluster_master_2_isolated,
    cluster_master_3,
    cluster_master_3_isolated,
    cluster_master_4,
    cluster_minion_1,
    cluster_minion_1_isolated,
    cluster_pillar_roots_path_isolated,
    cluster_pki_path,
    cluster_pki_path_isolated,
    cluster_shared_path,
)

# pylint: enable=unused-import


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Isolated-FS cluster masters with open_mode=False, used by
# test_isolated_salt_key_cli.py to exercise the salt-key CLI accept path
# (issue #70401).  Keeping these in the scenarios conftest so the integration
# fixtures that already pin open_mode=True for auto-accept scenarios stay
# unchanged.
# ---------------------------------------------------------------------------


def _closed_isolated_master_overrides(
    addr, peers, pki_paths, cache_paths, file_roots_paths, pillar_roots_paths
):
    overrides = _isolated_master_overrides(
        addr,
        peers,
        pki_paths,
        cache_paths,
        file_roots_paths,
        pillar_roots_paths,
    )
    overrides["open_mode"] = False
    overrides["auto_accept"] = False
    return overrides


def _noop_master_auth_callback(_master, _payload):
    """
    Replace salt-factories' default auto-accept hook (registered when
    ``open_mode: False``) with a no-op so these fixtures leave minion
    acceptance to the test driver.  Issue #70401 lives on the manual
    salt-key accept path; the default callback would short-circuit it.
    """
    return None


@pytest.fixture
def cluster_master_1_isolated_closed(
    request,
    salt_factories,
    cluster_pki_path_isolated,
    cluster_cache_path_isolated,
    cluster_file_roots_path_isolated,
    cluster_pillar_roots_path_isolated,
):
    config_defaults = {
        "open_mode": False,
        "auto_accept": False,
        "transport": request.config.getoption("--transport"),
    }
    config_overrides = _closed_isolated_master_overrides(
        "127.0.0.1",
        ["127.0.0.2", "127.0.0.3"],
        cluster_pki_path_isolated,
        cluster_cache_path_isolated,
        cluster_file_roots_path_isolated,
        cluster_pillar_roots_path_isolated,
    )
    factory = salt_factories.salt_master_daemon(
        "127.0.0.1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
        on_auth_event_callback=_noop_master_auth_callback,
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def cluster_master_2_isolated_closed(
    salt_factories,
    cluster_master_1_isolated_closed,
    cluster_pki_path_isolated,
    cluster_cache_path_isolated,
    cluster_file_roots_path_isolated,
    cluster_pillar_roots_path_isolated,
):
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.2", "up"])
    config_defaults = {
        "open_mode": False,
        "auto_accept": False,
        "transport": cluster_master_1_isolated_closed.config["transport"],
    }
    config_overrides = _closed_isolated_master_overrides(
        "127.0.0.2",
        ["127.0.0.1", "127.0.0.3"],
        cluster_pki_path_isolated,
        cluster_cache_path_isolated,
        cluster_file_roots_path_isolated,
        cluster_pillar_roots_path_isolated,
    )
    for key in ("ret_port", "publish_port"):
        config_overrides[key] = cluster_master_1_isolated_closed.config[key]
    factory = salt_factories.salt_master_daemon(
        "127.0.0.2",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
        on_auth_event_callback=_noop_master_auth_callback,
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def cluster_master_3_isolated_closed(
    salt_factories,
    cluster_master_1_isolated_closed,
    cluster_pki_path_isolated,
    cluster_cache_path_isolated,
    cluster_file_roots_path_isolated,
    cluster_pillar_roots_path_isolated,
):
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", "127.0.0.3", "up"])
    config_defaults = {
        "open_mode": False,
        "auto_accept": False,
        "transport": cluster_master_1_isolated_closed.config["transport"],
    }
    config_overrides = _closed_isolated_master_overrides(
        "127.0.0.3",
        ["127.0.0.1", "127.0.0.2"],
        cluster_pki_path_isolated,
        cluster_cache_path_isolated,
        cluster_file_roots_path_isolated,
        cluster_pillar_roots_path_isolated,
    )
    for key in ("ret_port", "publish_port"):
        config_overrides[key] = cluster_master_1_isolated_closed.config[key]
    factory = salt_factories.salt_master_daemon(
        "127.0.0.3",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
        on_auth_event_callback=_noop_master_auth_callback,
    )
    with factory.started(start_timeout=120):
        yield factory


@pytest.fixture
def cluster_minion_all(
    cluster_master_1,
    cluster_master_2,
    cluster_master_3,
    cluster_master_4,
):
    """
    A minion subscribed to all four cluster masters.

    Required for the ``test_fourth_master_joins_existing_cluster`` test because
    ``salt`` dispatches jobs through master 4's publish channel and the minion
    must be listening there to receive them.
    """
    port = cluster_master_1.config["ret_port"]
    config_overrides = {
        "master": [
            f"{cluster_master_1.config['interface']}:{port}",
            f"{cluster_master_2.config['interface']}:{port}",
            f"{cluster_master_3.config['interface']}:{port}",
            f"{cluster_master_4.config['interface']}:{port}",
        ],
        "master_type": "failover",
        "test.foo": "baz",
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = cluster_master_1.salt_minion_daemon(
        "cluster-minion-all",
        defaults={"transport": cluster_master_1.config["transport"]},
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=240):
        yield factory
