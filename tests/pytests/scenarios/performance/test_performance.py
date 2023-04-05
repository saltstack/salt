import os
import shutil
import time

import pytest
from pytestshellutils.utils import ports
from saltfactories.daemons import master
from saltfactories.daemons.container import SaltDaemon, SaltMinion
from saltfactories.utils import random_string

from salt.version import SaltVersionsInfo, __version__

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


# ---------------------- Previous Version Setup ----------------------


@pytest.fixture
def prev_version():
    return str(SaltVersionsInfo.previous_release().info[0])


@pytest.fixture
def curr_version():
    return str(SaltVersionsInfo.current_release().info[0])


@pytest.fixture
def prev_master_id():
    return random_string("master-performance-prev-", uppercase=False)


@pytest.fixture
def prev_master(
    request,
    salt_factories,
    host_docker_network_ip_address,
    network,
    prev_version,
    docker_client,
    prev_master_id,
):
    root_dir = salt_factories.get_root_dir_for_daemon(prev_master_id)
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
        prev_master_id,
        defaults=config_defaults,
        overrides=config_overrides,
        factory_class=ContainerMaster,
        image="ghcr.io/saltstack/salt-ci-containers/salt:{}".format(prev_version),
        base_script_args=["--log-level=debug"],
        container_run_kwargs={
            "network": network,
            "hostname": prev_master_id,
        },
        docker_client=docker_client,
        name=prev_master_id,
        start_timeout=120,
        max_start_attempts=1,
        skip_if_docker_client_not_connectable=True,
    )
    with factory.started():
        yield factory


@pytest.fixture
def prev_salt_cli(prev_master):
    return prev_master.salt_cli()


@pytest.fixture
def prev_salt_key_cli(prev_master):
    return prev_master.salt_key_cli()


@pytest.fixture
def prev_salt_run_cli(prev_master):
    return prev_master.salt_run_cli()


@pytest.fixture
def prev_minion_id():
    return random_string(
        "minion-performance-prev-",
        uppercase=False,
    )


@pytest.fixture
def prev_minion(
    prev_minion_id,
    prev_master,
    docker_client,
    prev_version,
    host_docker_network_ip_address,
    network,
    prev_master_id,
):
    config_overrides = {
        "master": prev_master_id,
        "user": False,
        "pytest-minion": {"log": {"host": host_docker_network_ip_address}},
    }
    factory = prev_master.salt_minion_daemon(
        prev_minion_id,
        overrides=config_overrides,
        factory_class=ContainerMinion,
        # SaltMinion kwargs
        name=prev_minion_id,
        image="ghcr.io/saltstack/salt-ci-containers/salt:{}".format(prev_version),
        docker_client=docker_client,
        start_timeout=120,
        pull_before_start=False,
        skip_if_docker_client_not_connectable=True,
        container_run_kwargs={
            "network": network,
            "hostname": prev_minion_id,
        },
        max_start_attempts=1,
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, prev_master, factory.id
    )
    with factory.started():
        yield factory


@pytest.fixture
def prev_sls(sls_contents, state_tree, tmp_path):
    sls_name = "prev"
    location = tmp_path / "prev" / "testfile"
    location.parent.mkdir()
    with pytest.helpers.temp_file(
        "{}.sls".format(sls_name), sls_contents.format(path=str(location)), state_tree
    ):
        yield sls_name


# ---------------------- Current Version Setup ----------------------


def _install_local_salt(factory):
    factory.run("pip install /saltcode")


@pytest.fixture
def curr_master_id():
    return random_string("master-performance-", uppercase=False)


@pytest.fixture
def curr_master(
    request,
    salt_factories,
    host_docker_network_ip_address,
    network,
    docker_client,
    curr_master_id,
):
    root_dir = salt_factories.get_root_dir_for_daemon(curr_master_id)
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
        curr_master_id,
        defaults=config_defaults,
        overrides=config_overrides,
        factory_class=ContainerMaster,
        image="ghcr.io/saltstack/salt-ci-containers/salt:current",
        base_script_args=["--log-level=debug"],
        container_run_kwargs={
            "network": network,
            "hostname": curr_master_id,
            # Bind the current code to a directory for pip installing
            "volumes": {
                os.environ["REPO_ROOT_DIR"]: {"bind": "/saltcode", "mode": "z"}
            },
        },
        docker_client=docker_client,
        name=curr_master_id,
        start_timeout=120,
        max_start_attempts=1,
        skip_if_docker_client_not_connectable=True,
    )

    factory.before_start(_install_local_salt, factory)
    with factory.started():
        yield factory


@pytest.fixture
def curr_salt_cli(curr_master):
    return curr_master.salt_cli()


@pytest.fixture
def curr_salt_run_cli(curr_master):
    return curr_master.salt_run_cli()


@pytest.fixture
def curr_salt_key_cli(curr_master):
    return curr_master.salt_key_cli()


@pytest.fixture
def curr_minion_id():
    return random_string(
        "minion-performance-curr-",
        uppercase=False,
    )


@pytest.fixture
def curr_minion(
    curr_minion_id,
    curr_master,
    docker_client,
    host_docker_network_ip_address,
    network,
    curr_master_id,
):
    config_overrides = {
        "master": curr_master_id,
        "user": False,
        "pytest-minion": {"log": {"host": host_docker_network_ip_address}},
    }
    factory = curr_master.salt_minion_daemon(
        curr_minion_id,
        overrides=config_overrides,
        factory_class=ContainerMinion,
        # SaltMinion kwargs
        name=curr_minion_id,
        image="ghcr.io/saltstack/salt-ci-containers/salt:current",
        docker_client=docker_client,
        start_timeout=120,
        pull_before_start=False,
        skip_if_docker_client_not_connectable=True,
        container_run_kwargs={
            "network": network,
            "hostname": curr_minion_id,
            # Bind the current code to a directory for pip installing
            "volumes": {
                os.environ["REPO_ROOT_DIR"]: {"bind": "/saltcode", "mode": "z"}
            },
        },
        max_start_attempts=1,
    )
    factory.before_start(_install_local_salt, factory)
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, curr_master, factory.id
    )
    with factory.started():
        yield factory


@pytest.fixture
def curr_sls(sls_contents, state_tree, tmp_path):
    sls_name = "curr"
    location = tmp_path / "curr" / "testfile"
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
        pytest.skip(
            f"Skipping test, one or more daemons failed to start: {expected} not found in {ret}"
        )


@pytest.mark.flaky(max_runs=4)
def test_performance(
    prev_salt_cli,
    prev_minion,
    prev_salt_run_cli,
    prev_salt_key_cli,
    prev_version,
    prev_master,
    state_tree,
    curr_salt_cli,
    curr_master,
    curr_salt_run_cli,
    curr_salt_key_cli,
    curr_minion,
    prev_sls,
    curr_sls,
    curr_version,
):
    # Copy all of the needed files to both master file roots directories
    subdir = random_string("performance-")
    shutil.copytree(
        state_tree, os.path.join(curr_master.config["file_roots"]["base"][0], subdir)
    )
    shutil.copytree(
        state_tree, os.path.join(prev_master.config["file_roots"]["base"][0], subdir)
    )

    # Wait for the old master and minion to start
    _wait_for_stdout(
        prev_version, prev_master.run, *prev_salt_run_cli.cmdline("--version")
    )
    salt_key_cmd = [
        comp
        for comp in prev_salt_key_cli.cmdline("-Ay")
        if not comp.startswith("--log-level")
    ]
    _wait_for_stdout(prev_minion.id, prev_master.run, *salt_key_cmd)
    _wait_for_stdout(
        "Salt: {}".format(prev_version),
        prev_master.run,
        *prev_salt_cli.cmdline("test.versions", minion_tgt=prev_minion.id),
    )

    # Wait for the new master and minion to start
    _wait_for_stdout(
        curr_version, curr_master.run, *curr_salt_run_cli.cmdline("--version")
    )
    curr_key_cmd = [
        comp
        for comp in curr_salt_key_cli.cmdline("-Ay")
        if not comp.startswith("--log-level")
    ]
    _wait_for_stdout(curr_minion.id, curr_master.run, *curr_key_cmd)
    _wait_for_stdout(
        "Salt: {}".format(curr_version),
        curr_master.run,
        *curr_salt_cli.cmdline("test.versions", minion_tgt=curr_minion.id),
    )

    # Let's now apply the states
    applies = os.environ.get("SALT_PERFORMANCE_TEST_APPLIES", 3)

    def _gather_durations(ret, minion_id):
        """
        Get the total duration for the state run.

        We skip if anything fails here.  We aren't testing state success, just performance.
        """
        if isinstance(ret.data, dict) and isinstance(
            ret.data.get(minion_id, None), dict
        ):
            duration = 0
            for _, state_ret in ret.data[minion_id].items():
                try:
                    duration += state_ret["duration"]
                except KeyError:
                    break
            else:
                return duration
        pytest.skip("Something went wrong with the states, skipping.")

    prev_duration = 0
    curr_duration = 0

    for _ in range(applies):
        prev_state_ret = prev_master.run(
            *prev_salt_cli.cmdline(
                "state.apply", f"{subdir}.{prev_sls}", minion_tgt=prev_minion.id
            )
        )
        prev_duration += _gather_durations(prev_state_ret, prev_minion.id)

    for _ in range(applies):
        curr_state_ret = curr_master.run(
            *curr_salt_cli.cmdline(
                "state.apply", f"{subdir}.{curr_sls}", minion_tgt=curr_minion.id
            )
        )
        curr_duration += _gather_durations(curr_state_ret, curr_minion.id)

    # We account for network slowness, etc... here.
    # There is a hard balance here as far as a threshold.
    # We need to make sure there are no drastic slowdowns,
    # but also take into account system and network nuances.
    # In theory we could set a hard cap for the duration,
    # something like 500 ms and only run the current version,
    # but we will see if this ever becomes too flaky
    assert curr_duration <= 1.25 * prev_duration
