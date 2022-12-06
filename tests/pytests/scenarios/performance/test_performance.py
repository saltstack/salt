import time

import pytest
from pytestshellutils.utils import ports
from saltfactories.daemons import master
from saltfactories.daemons.container import SaltDaemon, SaltMinion
from saltfactories.utils import random_string


class ContainerMaster(SaltDaemon, master.SaltMaster):
    """
    Containerized salt master that has no check events
    """

    def get_display_name(self):
        return master.SaltMaster.get_display_name(self)

    def get_check_events(self):
        return []


class ContainerMinion(SaltMinion):
    """
    Containerized salt minion that has no check events
    """

    def get_check_events(self):
        return []


@pytest.fixture(scope="session")
def compat_salt_version():
    return "3004"


@pytest.fixture(scope="session")
def master_id(compat_salt_version):
    return random_string(
        "master-performance-{}-".format(compat_salt_version), uppercase=False
    )


@pytest.fixture(scope="package")
def container_master(
    request,
    salt_factories,
    host_docker_network_ip_address,
    network,
    state_tree,
    pillar_tree,
    compat_salt_version,
    docker_client,
    master_id,
):
    root_dir = salt_factories.get_root_dir_for_daemon(master_id)
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(exist_ok=True)

    config_defaults = {
        "root_dir": str(root_dir),
        "transport": request.config.getoption("--transport"),
        "user": False,
    }
    publish_port = ports.get_unused_localhost_port()
    ret_port = ports.get_unused_localhost_port()
    config_overrides = {
        "interface": "0.0.0.0",
        "publish_port": publish_port,
        "ret_port": ret_port,
        "log_level_logfile": "quiet",
        "pytest-master": {
            "log": {"host": host_docker_network_ip_address},
        },
    }

    config_overrides.update(
        {
            "file_roots": {"base": [str(state_tree)]},
            "pillar_roots": {"base": [str(pillar_tree)]},
        }
    )
    factory = salt_factories.salt_master_daemon(
        master_id,
        defaults=config_defaults,
        overrides=config_overrides,
        factory_class=ContainerMaster,
        image="ghcr.io/saltstack/salt-ci-containers/salt:{}".format(
            compat_salt_version
        ),
        base_script_args=["--log-level=debug"],
        container_run_kwargs={
            # "ports": {
            #     f"{publish_port}/tcp": publish_port,
            #     f"{ret_port}/tcp": ret_port,
            # },
            "network": network,
            "hostname": master_id,
        },
        docker_client=docker_client,
        name=master_id,
        start_timeout=120,
        max_start_attempts=1,
        skip_if_docker_client_not_connectable=True,
    )
    with factory.started():
        yield factory


@pytest.fixture
def salt_cli(container_master):
    return container_master.salt_cli()


@pytest.fixture
def salt_key_cli(container_master):
    return container_master.salt_key_cli()


@pytest.fixture
def salt_run_cli(container_master):
    return container_master.salt_run_cli()


@pytest.fixture()
def minion_id(compat_salt_version):
    return random_string(
        "minion-performance-{}-".format(compat_salt_version),
        uppercase=False,
    )


@pytest.mark.skip_if_binaries_missing("docker")
@pytest.fixture()
def container_minion(
    minion_id,
    container_master,
    docker_client,
    compat_salt_version,
    host_docker_network_ip_address,
    network,
    master_id,
):
    config_overrides = {
        "master": master_id,
        "user": False,
        "pytest-minion": {"log": {"host": host_docker_network_ip_address}},
    }
    factory = container_master.salt_minion_daemon(
        minion_id,
        overrides=config_overrides,
        factory_class=ContainerMinion,
        # SaltMinion kwargs
        name=minion_id,
        image="ghcr.io/saltstack/salt-ci-containers/salt:{}".format(
            compat_salt_version
        ),
        docker_client=docker_client,
        start_timeout=120,
        pull_before_start=False,
        skip_if_docker_client_not_connectable=True,
        container_run_kwargs={
            "network": network,
            "hostname": minion_id,
        },
        max_start_attempts=1,
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, container_master, factory.id
    )
    with factory.started():
        yield factory


def _wait_for_stdout(expected, func, *args, timeout=120, **kwargs):
    start = time.time()
    while time.time() < start + timeout:
        ret = func(*args, **kwargs)
        if ret and ret.stdout and expected in ret.stdout:
            break
        time.sleep(1)
    else:
        pytest.skip("Skipping test, one or more daemons failed to start")


def test_performance(
    salt_cli,
    container_minion,
    salt_run_cli,
    salt_key_cli,
    compat_salt_version,
    container_master,
):
    _wait_for_stdout(
        compat_salt_version,
        container_master.run,
        *salt_run_cli.cmdline("--versions-report")
    )
    salt_key_cmd = [
        comp
        for comp in salt_key_cli.cmdline("-Ay")
        if not comp.startswith("--log-level")
    ]
    _wait_for_stdout(container_minion.id, container_master.run, *salt_key_cmd)

    versions_ret = container_master.run(
        *salt_cli.cmdline("test.versions", minion_tgt=container_minion.id)
    )
    assert compat_salt_version in versions_ret.stdout
