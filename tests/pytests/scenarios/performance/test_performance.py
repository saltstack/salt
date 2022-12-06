import os
import shutil
import time

import pytest
from pytestshellutils.utils import ports
from saltfactories.daemons import master
from saltfactories.daemons.container import SaltDaemon, SaltMinion
from saltfactories.utils import random_string

from salt.version import SaltVersionsInfo

pytestmark = [pytest.mark.skip_if_binaries_missing("docker")]


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


# ---------------------- Docker Setup ----------------------


@pytest.fixture(scope="package")
def prev_version():
    return str(SaltVersionsInfo.previous_release().info[0])


@pytest.fixture(scope="package")
def container_master_id(prev_version):
    return random_string("master-performance-{}-".format(prev_version), uppercase=False)


@pytest.fixture(scope="package")
def container_master(
    request,
    salt_factories,
    host_docker_network_ip_address,
    network,
    prev_version,
    docker_client,
    container_master_id,
):
    root_dir = salt_factories.get_root_dir_for_daemon(container_master_id)
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

    factory = salt_factories.salt_master_daemon(
        container_master_id,
        defaults=config_defaults,
        overrides=config_overrides,
        factory_class=ContainerMaster,
        image="ghcr.io/saltstack/salt-ci-containers/salt:{}".format(prev_version),
        base_script_args=["--log-level=debug"],
        container_run_kwargs={
            "network": network,
            "hostname": container_master_id,
        },
        docker_client=docker_client,
        name=container_master_id,
        start_timeout=120,
        max_start_attempts=1,
        skip_if_docker_client_not_connectable=True,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="package")
def container_salt_cli(container_master):
    return container_master.salt_cli()


@pytest.fixture(scope="package")
def container_salt_key_cli(container_master):
    return container_master.salt_key_cli()


@pytest.fixture(scope="package")
def container_salt_run_cli(container_master):
    return container_master.salt_run_cli()


@pytest.fixture(scope="package")
def container_minion_id(prev_version):
    return random_string(
        "minion-performance-{}-".format(prev_version),
        uppercase=False,
    )


@pytest.fixture(scope="package")
def container_minion(
    container_minion_id,
    container_master,
    docker_client,
    prev_version,
    host_docker_network_ip_address,
    network,
    container_master_id,
):
    config_overrides = {
        "master": container_master_id,
        "user": False,
        "pytest-minion": {"log": {"host": host_docker_network_ip_address}},
    }
    factory = container_master.salt_minion_daemon(
        container_minion_id,
        overrides=config_overrides,
        factory_class=ContainerMinion,
        # SaltMinion kwargs
        name=container_minion_id,
        image="ghcr.io/saltstack/salt-ci-containers/salt:{}".format(prev_version),
        docker_client=docker_client,
        start_timeout=120,
        pull_before_start=False,
        skip_if_docker_client_not_connectable=True,
        container_run_kwargs={
            "network": network,
            "hostname": container_minion_id,
        },
        max_start_attempts=1,
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, container_master, factory.id
    )
    with factory.started():
        yield factory


@pytest.fixture
def container_sls(sls_contents, state_tree, tmp_path):
    sls_name = "container"
    location = tmp_path / "container" / "testfile"
    location.parent.mkdir()
    with pytest.helpers.temp_file(
        "{}.sls".format(sls_name), sls_contents.format(path=str(location)), state_tree
    ):
        yield sls_name


# ---------------------- Local Setup ----------------------


@pytest.fixture(scope="package")
def master_id():
    return random_string("master-performance-", uppercase=False)


@pytest.fixture(scope="package")
def salt_master(
    request,
    salt_factories,
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
        "interface": "127.0.0.1",
        "publish_port": publish_port,
        "ret_port": ret_port,
        "log_level_logfile": "quiet",
    }

    factory = salt_factories.salt_master_daemon(
        master_id,
        defaults=config_defaults,
        overrides=config_overrides,
        start_timeout=120,
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="package")
def salt_cli(salt_master):
    return salt_master.salt_cli()


@pytest.fixture(scope="package")
def minion_id():
    return random_string(
        "minion-performance-",
        uppercase=False,
    )


@pytest.fixture(scope="package")
def salt_minion(
    minion_id,
    salt_master,
):
    config_overrides = {
        "user": False,
    }
    factory = salt_master.salt_minion_daemon(
        minion_id,
        overrides=config_overrides,
        start_timeout=120,
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, factory.id
    )
    with factory.started():
        yield factory


@pytest.fixture
def local_sls(sls_contents, state_tree, tmp_path):
    sls_name = "local"
    location = tmp_path / "local" / "testfile"
    location.parent.mkdir()
    with pytest.helpers.temp_file(
        "{}.sls".format(sls_name), sls_contents.format(path=str(location)), state_tree
    ):
        yield sls_name


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
    container_salt_cli,
    container_minion,
    container_salt_run_cli,
    container_salt_key_cli,
    prev_version,
    container_master,
    state_tree,
    salt_cli,
    salt_minion,
    salt_master,
    container_sls,
    local_sls,
):
    # Copy all of the needed files to both master file roots directories
    shutil.copytree(
        state_tree, salt_master.config["file_roots"]["base"][0], dirs_exist_ok=True
    )
    shutil.copytree(
        state_tree, container_master.config["file_roots"]["base"][0], dirs_exist_ok=True
    )

    # Wait for the container master and minion to start
    _wait_for_stdout(
        prev_version, container_master.run, *container_salt_run_cli.cmdline("--version")
    )
    salt_key_cmd = [
        comp
        for comp in container_salt_key_cli.cmdline("-Ay")
        if not comp.startswith("--log-level")
    ]
    _wait_for_stdout(container_minion.id, container_master.run, *salt_key_cmd)
    _wait_for_stdout(
        "Salt: {}".format(prev_version),
        container_master.run,
        *container_salt_cli.cmdline("test.versions", minion_tgt=container_minion.id)
    )

    # Let's now apply the states
    applies = os.environ.get("SALT_PERFORMANCE_TEST_APPLIES", 3)
    container_salt_cmd = container_salt_cli.cmdline(
        "state.apply", container_sls, minion_tgt=container_minion.id
    )

    start = time.time()
    for _ in range(applies):
        container_state_ret = container_master.run(*container_salt_cmd)
        assert container_state_ret.data
    container_duration = time.time() - start

    start = time.time()
    for _ in range(applies):
        local_state_ret = salt_cli.run(
            "state.apply", local_sls, minion_tgt=salt_minion.id
        )
        assert local_state_ret.data
    local_duration = time.time() - start

    assert local_duration <= 1.01 * container_duration
