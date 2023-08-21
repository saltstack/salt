import logging
import subprocess

import pytest

import salt.utils.platform

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
    }
    factory = salt_factories.salt_master_daemon(
        "127.0.0.1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


# @pytest.fixture(scope="package")
# def cluster_master_1_salt_cli(cluster_master_1):
#    return cluster__master_1.salt_cli(timeout=120)
#
#
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


#
# @pytest.fixture(scope="package")
# def cluster_master_2_salt_cli(cluster_master_2):
#    return cluster_master_2.salt_cli(timeout=120)
#
#
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
    }
    factory = cluster_master_1.salt_minion_daemon(
        "cluster-minion-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


#
#
# @pytest.fixture(scope="package")
# def cluster_minion_2(cluster_master_2):
#    config_defaults = {
#        "transport": cluster_master_2.config["transport"],
#    }
#
#    port = cluster_master_2.config["ret_port"]
#    addr = cluster_master_2.config["interface"]
#    config_overrides = {
#        "master": f"{port}:{addr}",
#        "test.foo": "baz",
#    }
#    factory = salt_mm_master_1.salt_minion_daemon(
#        "cluster-minion-2",
#        defaults=config_defaults,
#        overrides=config_overrides,
#        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
#    )
#    with factory.started(start_timeout=120):
#        yield factory
#
#
#
# @pytest.fixture(scope="package")
# def run_salt_cmds():
#    def _run_salt_cmds_fn(clis, minions):
#        """
#        Run test.ping from all clis to all minions
#        """
#        returned_minions = []
#        minion_instances = {minion.id: minion for minion in minions}
#        clis_to_check = {minion.id: list(clis) for minion in minions}
#
#        attempts = 6
#        timeout = 5
#        if salt.utils.platform.spawning_platform():
#            timeout *= 2
#        while attempts:
#            if not clis_to_check:
#                break
#            for minion in list(clis_to_check):
#                if not clis_to_check[minion]:
#                    clis_to_check.pop(minion)
#                    continue
#                for cli in list(clis_to_check[minion]):
#                    try:
#                        ret = cli.run(
#                            "--timeout={}".format(timeout),
#                            "test.ping",
#                            minion_tgt=minion,
#                            _timeout=2 * timeout,
#                        )
#                        if ret.returncode == 0 and ret.data is True:
#                            returned_minions.append((cli, minion_instances[minion]))
#                            clis_to_check[minion].remove(cli)
#                    except FactoryTimeout:
#                        log.debug(
#                            "Failed to execute test.ping from %s to %s.",
#                            cli.get_display_name(),
#                            minion,
#                        )
#            time.sleep(1)
#            attempts -= 1
#
#        return returned_minions
#
#    return _run_salt_cmds_fn
