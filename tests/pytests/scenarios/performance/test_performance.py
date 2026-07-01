import logging
import os
import shutil

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
    # Check if image exists first
    ret = shell.run("docker", "image", "inspect", container, check=False)
    if ret.returncode == 0:
        return container
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
    # Check if image exists first
    ret = shell.run("docker", "image", "inspect", container, check=False)
    if ret.returncode == 0:
        return container
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
        "worker_pools_enabled": True,
        "worker_pools": {
            "fast": {
                "worker_count": 2,
                "commands": [
                    "test.ping",
                    "test.echo",
                    "test.fib",
                    "grains.items",
                    "sys.doc",
                    "pillar.items",
                    "runner.test.arg",
                    "auth",
                ],
            },
            "general": {
                "worker_count": 3,
                "commands": ["*"],
            },
        },
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
        "worker_pools_enabled": True,
        "worker_pools": {
            "fast": {
                "worker_count": 2,
                "commands": [
                    "test.ping",
                    "test.echo",
                    "test.fib",
                    "grains.items",
                    "sys.doc",
                    "pillar.items",
                    "runner.test.arg",
                    "auth",
                ],
            },
            "general": {
                "worker_count": 3,
                "commands": ["*"],
            },
        },
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
    factory.python_executable = "python3"
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key, prev_master, factory.id
    )
    factory.before_start(_install_salt_in_container, factory)
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


def _container_python_executable(container):
    """
    Pick a python executable inside the container whose major.minor matches
    one of the lockfiles in ``requirements/static/pkg/``.

    Older ``salt`` reference images (e.g. ``salt:3005``) ship the salt onedir
    on Python 3.7 as ``/usr/local/bin/python3`` but also carry the distro's
    own ``/usr/bin/python3`` (3.11 on Debian 12). The 3.7 interpreter cannot
    install the modern lockfile (``aiohappyeyeballs==2.6.1`` requires
    ``>=3.9``), so prefer whichever python in the container matches an
    available lockfile.
    """
    candidates = ("python3", "/usr/bin/python3", "/usr/local/bin/python3")
    available_lockdirs = {
        p.name
        for p in (CODE_DIR / "requirements" / "static" / "pkg").iterdir()
        if p.is_dir() and p.name.startswith("py")
    }
    seen = set()
    for candidate in candidates:
        ret = container.run(
            candidate,
            "-c",
            "import sys; print('{}.{}'.format(*sys.version_info))",
        )
        if ret.returncode != 0 or not ret.stdout:
            continue
        version = ret.stdout.strip()
        if version in seen:
            continue
        seen.add(version)
        if f"py{version}" in available_lockdirs:
            return candidate, version
    pytest.skip(
        "No python interpreter inside the container matches an available "
        f"requirements lockfile (tried {sorted(seen)})."
    )


def _install_salt_in_container(container):
    python_executable, requirements_py_version = _container_python_executable(container)

    # Make sure the chosen interpreter has a working ``pip`` available. The
    # distro's system python on the salt reference images doesn't always ship
    # pip (e.g. salt:3005's /usr/bin/python3 == python3.11 has no pip); the
    # onedir interpreter does. Try ensurepip first, then fall back to the
    # distro's package manager.
    ret = container.run(python_executable, "-m", "pip", "--version")
    if ret.returncode != 0:
        ret = container.run(python_executable, "-m", "ensurepip", "--upgrade")
        log.debug("ensurepip in the container: %s", ret)
        if ret.returncode != 0:
            apt_ret = container.run(
                "sh",
                "-c",
                "apt-get update >/dev/null && apt-get install -y python3-pip",
            )
            log.debug("apt-get install python3-pip in the container: %s", apt_ret)
            assert apt_ret.returncode == 0, apt_ret.stderr
        ret = container.run(python_executable, "-m", "pip", "--version")
        assert ret.returncode == 0, ret.stderr

    ret = container.run(
        "env",
        "SETUPTOOLS_USE_DISTUTILS=stdlib",
        python_executable,
        "-m",
        "pip",
        "install",
        "--break-system-packages",
        "-r",
        f"/salt/requirements/static/pkg/py{requirements_py_version}/linux.lock",
    )
    log.debug("Install Salt package requirements in the container: %s", ret)
    assert ret.returncode == 0, ret.stderr
    ret = container.run(
        "env",
        "SETUPTOOLS_USE_DISTUTILS=stdlib",
        python_executable,
        "-m",
        "pip",
        "install",
        "--break-system-packages",
        f"--constraint=/salt/requirements/static/ci/py{requirements_py_version}/linux.lock",
        "/salt",
    )
    log.debug("Install Salt in the container: %s", ret)
    assert ret.returncode == 0, ret.stderr


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
        "worker_pools_enabled": True,
        "worker_pools": {
            "fast": {
                "worker_count": 2,
                "commands": [
                    "test.ping",
                    "test.echo",
                    "test.fib",
                    "grains.items",
                    "sys.doc",
                    "pillar.items",
                    "runner.test.arg",
                    "auth",
                ],
            },
            "general": {
                "worker_count": 3,
                "commands": ["*"],
            },
        },
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
        "worker_pools_enabled": True,
        "worker_pools": {
            "fast": {
                "worker_count": 2,
                "commands": [
                    "test.ping",
                    "test.echo",
                    "test.fib",
                    "grains.items",
                    "sys.doc",
                    "pillar.items",
                    "runner.test.arg",
                    "auth",
                ],
            },
            "general": {
                "worker_count": 3,
                "commands": ["*"],
            },
        },
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


@pytest.mark.skip("GREAT MODULE MIGRATION")
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
    assert curr_duration <= 1.75 * prev_duration
