import logging
import os
import shutil
import sys

import pytest
from pytestshellutils.utils import ports
from saltfactories.daemons.container import SaltMaster, SaltMinion
from saltfactories.utils import random_string

from salt.version import SaltVersionsInfo
from tests.conftest import CODE_DIR

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skip_on_photonos,
    pytest.mark.skip_if_binaries_missing("docker"),
]


@pytest.fixture
def prev_version():
    return str(SaltVersionsInfo.previous_release().info[0])


@pytest.fixture
def prev_container_image(shell, prev_version):
    container = f"ghcr.io/saltstack/salt-ci-containers/salt:{prev_version}"
    ret = shell.run("docker", "pull", container, check=False)
    if ret.returncode:
        pytest.skip(f"Failed to pull docker image '{container}':\n{ret}")
    return container


@pytest.fixture
def curr_version():
    return str(SaltVersionsInfo.current_release().info[0])


@pytest.fixture
def curr_container_image(shell):
    container = "ghcr.io/saltstack/salt-ci-containers/salt:latest"
    ret = shell.run("docker", "pull", container, check=False)
    if ret.returncode:
        pytest.skip(f"Failed to pull docker image '{container}':\n{ret}")
    return container


@pytest.fixture
def prev_master_id():
    return random_string("master-perf-prev-", uppercase=False)


@pytest.fixture
def prev_master(
    request,
    salt_factories,
    host_docker_network_ip_address,
    docker_network_name,
    prev_version,
    prev_master_id,
    prev_container_image,
):
    root_dir = salt_factories.get_root_dir_for_daemon(prev_master_id)
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(exist_ok=True)

    config_defaults = {
        "root_dir": str(root_dir),
        "transport": request.config.getoption("--transport"),
        "user": "root",
    }
    config_overrides = {
        "open_mode": True,
        "interface": "0.0.0.0",
        "publish_port": ports.get_unused_localhost_port(),
        "ret_port": ports.get_unused_localhost_port(),
        "log_level_logfile": "quiet",
        "pytest-master": {
            "log": {"host": host_docker_network_ip_address},
            "returner_address": {"host": host_docker_network_ip_address},
        },
    }

    factory = salt_factories.salt_master_daemon(
        prev_master_id,
        name=prev_master_id,
        defaults=config_defaults,
        overrides=config_overrides,
        factory_class=SaltMaster,
        base_script_args=["--log-level=debug"],
        image=prev_container_image,
        container_run_kwargs={
            "network": docker_network_name,
            "hostname": prev_master_id,
        },
        start_timeout=120,
        max_start_attempts=3,
        pull_before_start=False,
        skip_on_pull_failure=True,
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
        "minion-perf-prev-",
        uppercase=False,
    )


@pytest.fixture
def prev_minion(
    prev_minion_id,
    prev_master,
    prev_version,
    host_docker_network_ip_address,
    docker_network_name,
    prev_container_image,
):
    config_overrides = {
        "master": prev_master.id,
        "open_mode": True,
        "user": "root",
        "pytest-minion": {
            "log": {"host": host_docker_network_ip_address},
            "returner_address": {"host": host_docker_network_ip_address},
        },
    }
    factory = prev_master.salt_minion_daemon(
        prev_minion_id,
        name=prev_minion_id,
        overrides=config_overrides,
        factory_class=SaltMinion,
        base_script_args=["--log-level=debug"],
        image=prev_container_image,
        container_run_kwargs={
            "network": docker_network_name,
            "hostname": prev_minion_id,
        },
        start_timeout=120,
        max_start_attempts=3,
        pull_before_start=False,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    factory.python_executable = "python3"
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
        f"{sls_name}.sls", sls_contents.format(path=str(location)), state_tree
    ):
        yield sls_name


def _install_salt_in_container(container):
    ret = container.run(
        "python3",
        "-c",
        "import sys; sys.stderr.write('{}.{}'.format(*sys.version_info))",
    )
    assert ret.returncode == 0
    if not ret.stdout:
        requirements_py_version = "{}.{}".format(*sys.version_info)
    else:
        requirements_py_version = ret.stdout.strip()

    ret = container.run(
        "python3",
        "-m",
        "pip",
        "install",
        f"--constraint=/salt/requirements/static/ci/py{requirements_py_version}/linux.txt",
        "/salt",
    )
    log.debug("Install Salt in the container: %s", ret)
    assert ret.returncode == 0


@pytest.fixture
def curr_master_id():
    return random_string("master-perf-curr-", uppercase=False)


@pytest.fixture
def curr_master(
    request,
    salt_factories,
    host_docker_network_ip_address,
    docker_network_name,
    curr_master_id,
    curr_container_image,
):
    root_dir = salt_factories.get_root_dir_for_daemon(curr_master_id)
    conf_dir = root_dir / "conf"
    conf_dir.mkdir(exist_ok=True)

    config_defaults = {
        "root_dir": str(root_dir),
        "transport": request.config.getoption("--transport"),
        "user": "root",
    }
    publish_port = ports.get_unused_localhost_port()
    ret_port = ports.get_unused_localhost_port()
    config_overrides = {
        "open_mode": True,
        "interface": "0.0.0.0",
        "publish_port": publish_port,
        "ret_port": ret_port,
        "log_level_logfile": "quiet",
        "pytest-master": {
            "log": {"host": host_docker_network_ip_address},
            "returner_address": {"host": host_docker_network_ip_address},
        },
    }

    factory = salt_factories.salt_master_daemon(
        curr_master_id,
        name=curr_master_id,
        defaults=config_defaults,
        overrides=config_overrides,
        factory_class=SaltMaster,
        base_script_args=["--log-level=debug"],
        image=curr_container_image,
        container_run_kwargs={
            "network": docker_network_name,
            "hostname": curr_master_id,
            # Bind the current code to a directory for pip installing
            "volumes": {
                str(CODE_DIR): {"bind": "/salt", "mode": "z"},
            },
        },
        start_timeout=120,
        max_start_attempts=3,
        pull_before_start=False,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )

    factory.before_start(_install_salt_in_container, factory)
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
        "minion-perf-curr-",
        uppercase=False,
    )


@pytest.fixture
def curr_minion(
    curr_minion_id,
    curr_master,
    host_docker_network_ip_address,
    docker_network_name,
    curr_container_image,
):
    config_overrides = {
        "master": curr_master.id,
        "open_mode": True,
        "user": "root",
        "pytest-minion": {
            "log": {"host": host_docker_network_ip_address},
            "returner_address": {"host": host_docker_network_ip_address},
        },
    }
    factory = curr_master.salt_minion_daemon(
        curr_minion_id,
        name=curr_minion_id,
        overrides=config_overrides,
        factory_class=SaltMinion,
        base_script_args=["--log-level=debug"],
        image=curr_container_image,
        container_run_kwargs={
            "network": docker_network_name,
            "hostname": curr_minion_id,
            # Bind the current code to a directory for pip installing
            "volumes": {
                str(CODE_DIR): {"bind": "/salt", "mode": "z"},
            },
        },
        start_timeout=120,
        max_start_attempts=3,
        pull_before_start=False,
        skip_on_pull_failure=True,
        skip_if_docker_client_not_connectable=True,
    )
    factory.before_start(_install_salt_in_container, factory)
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
        f"{sls_name}.sls", sls_contents.format(path=str(location)), state_tree
    ):
        yield sls_name


@pytest.fixture
def perf_state_name(state_tree, curr_master, prev_master):

    # Copy all of the needed files to both master file roots directories
    subdir = random_string("perf-state-")
    shutil.copytree(
        state_tree, os.path.join(curr_master.config["file_roots"]["base"][0], subdir)
    )
    shutil.copytree(
        state_tree, os.path.join(prev_master.config["file_roots"]["base"][0], subdir)
    )
    return subdir


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
    perf_state_name,
):
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
                "state.apply",
                f"{perf_state_name}.{prev_sls}",
                minion_tgt=prev_minion.id,
            )
        )
        prev_duration += _gather_durations(prev_state_ret, prev_minion.id)

    for _ in range(applies):
        curr_state_ret = curr_master.run(
            *curr_salt_cli.cmdline(
                "state.apply",
                f"{perf_state_name}.{curr_sls}",
                minion_tgt=curr_minion.id,
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
