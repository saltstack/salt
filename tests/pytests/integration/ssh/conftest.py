import logging
import os
import platform

import pytest

from tests.support.helpers import system_python_version
from tests.support.pytest.helpers import reap_stray_processes

log = logging.getLogger(__name__)


@pytest.fixture(scope="session", autouse=True)
def relenv_tarball_cached(tmp_path_factory):
    """
    Pre-cache the relenv tarball once for the entire test session to a shared location.
    This avoids downloading it multiple times across different test modules.
    Runs automatically at session start (autouse=True).
    """
    # Import here to avoid issues if salt is not installed
    import tempfile

    import salt.utils.relenv

    # Use a shared system temp directory that persists across test master instances
    # This allows all tests in the session to share the same cached tarball
    shared_cache = os.path.join(tempfile.gettempdir(), "salt_ssh_test_relenv_cache")
    os.makedirs(shared_cache, exist_ok=True)

    # Detect OS and architecture
    kernel = platform.system().lower()
    if kernel == "darwin":
        kernel = "darwin"
    elif kernel == "windows":
        kernel = "windows"
    else:
        kernel = "linux"

    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        os_arch = "x86_64"
    elif machine in ("aarch64", "arm64"):
        os_arch = "arm64"
    else:
        os_arch = machine

    log.info(
        "Pre-caching relenv tarball for %s/%s in shared cache: %s",
        kernel,
        os_arch,
        shared_cache,
    )

    try:
        # Download and cache the tarball to the shared location
        tarball_path = salt.utils.relenv.gen_relenv(shared_cache, kernel, os_arch)
        log.info("Relenv tarball cached at: %s", tarball_path)

        # Verify the tarball exists
        if os.path.exists(tarball_path):
            file_size = os.path.getsize(tarball_path) / (1024 * 1024)  # Size in MB
            log.info("Cached tarball size: %.2f MB", file_size)

            # Set environment variable so salt.utils.relenv can find it
            # This allows individual test masters to copy from the shared cache
            os.environ["SALT_SSH_TEST_RELENV_CACHE"] = shared_cache
            return tarball_path
        else:
            log.warning(
                "Tarball download completed but file not found at: %s", tarball_path
            )
            return None
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Broad exception is intentional - we don't want relenv caching failures to break test setup
        log.warning("Failed to pre-cache relenv tarball: %s", e)
        return None


@pytest.fixture(scope="module", params=["thin", "relenv"], ids=["thin", "relenv"])
def ssh_deployment_type(request):
    """
    Fixture to parameterize tests with both thin and relenv deployments.
    The relenv_tarball_cached autouse fixture pre-caches the tarball at session start.
    """
    return request.param


@pytest.fixture(scope="function")
def salt_ssh_cli_parameterized(
    ssh_deployment_type,
    salt_master,
    salt_ssh_roster_file,
    sshd_config_dir,
    known_hosts_file,
):
    """
    Parameterized salt-ssh CLI fixture that tests with both thin and relenv deployments.

    Note: This uses function scope (not module scope) to ensure each test gets a fresh
    SSH instance. This is necessary because the SSH class conditionally initializes
    self.thin based on opts['relenv'], and with parametrized tests, we need a new
    instance for each deployment type to avoid shared state issues.
    """
    assert salt_master.is_running()
    cli = salt_master.salt_ssh_cli(
        timeout=180,
        roster_file=salt_ssh_roster_file,
        target_host="localhost",
        client_key=str(sshd_config_dir / "client_key"),
    )

    # Wrap the run method to inject --relenv flag when needed
    original_run = cli.run

    def run_with_deployment(*args, **kwargs):
        if ssh_deployment_type == "relenv":
            # Filter out -t/--thin flags which are incompatible with --relenv
            filtered_args = tuple(arg for arg in args if arg not in ("-t", "--thin"))
            # Insert --relenv flag at the beginning
            args = ("--relenv",) + filtered_args
        return original_run(*args, **kwargs)

    cli.run = run_with_deployment
    return cli


@pytest.fixture(scope="package", autouse=True)
def _auto_skip_on_system_python_too_recent(grains):
    if (
        grains["osfinger"] in ("Fedora Linux-40", "Ubuntu-24.04", "Debian-13")
        or grains["os_family"] == "Arch"
    ):
        pytest.skip(
            "System ships with a version of python that is too recent for salt-ssh tests",
            # Actually, the problem is that the tornado we ship is not prepared for Python 3.12,
            # and it imports `ssl` and checks if the `match_hostname` function is defined, which
            # has been deprecated since Python 3.7, so, the logic goes into trying to import
            # backports.ssl-match-hostname which is not installed on the system.
            # Debian 13 ships with Python 3.13 which has similar compatibility issues.
        )
    if system_python_version() < (3, 10):
        pytest.skip("System python too old for these tests")


@pytest.fixture(scope="package", autouse=True)
def _auto_skip_on_buggy_openssh(grains):
    """
    Skip SSH tests on systems with buggy OpenSSH versions that break salt-ssh.

    Photon OS 5 version 9.3p2-18 has a bug that causes
    "vdollar_percent_expand: NULL replacement for token n" errors
    when using the User config option that salt-ssh depends on.
    """
    if not grains["osfinger"].startswith("VMware Photon OS-5"):
        return

    import subprocess  # pylint: disable=import-outside-toplevel

    try:
        result = subprocess.run(
            ["rpm", "-q", "openssh-server"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        installed_version = result.stdout.strip()

        # Check for the specific buggy version
        if installed_version in [
            "openssh-server-9.3p2-18.ph5.x86_64",
            "openssh-server-9.3p2-18.ph5.aarch64",
        ]:
            pytest.skip(
                f"Photon OS OpenSSH {installed_version} has a bug that breaks salt-ssh. "
                "See: https://github.com/saltstack/salt/issues/xxxxx"
            )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        # If we can't check the version, don't skip
        pass


@pytest.fixture(autouse=True)
def _reap_stray_processes():
    # when tests timeout, we migth leave child processes behind
    # nuke them
    with reap_stray_processes():
        # Run test
        yield


@pytest.fixture(scope="module")
def state_tree(base_env_state_tree_root_dir):
    # Remove unused import from top file to avoid salt-ssh file sync issues
    # Note: top file references "basic" but we create "test.sls" - this appears
    # intentional as tests run state.sls directly and don't use the top file
    top_file = """
    base:
      'localhost':
        - basic
      '127.0.0.1':
        - basic
    """
    map_file = """
    {%- set abc = "def" %}
    """
    # State file imports from map.jinja - this is what we're testing
    state_file = """
    {%- from "map.jinja" import abc with context %}
    Ok with {{ abc }}:
      test.succeed_with_changes
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    map_tempfile = pytest.helpers.temp_file(
        "map.jinja", map_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "test.sls", state_file, base_env_state_tree_root_dir
    )
    with top_tempfile, map_tempfile, state_tempfile:
        yield


@pytest.fixture(scope="module")
def state_tree_dir(base_env_state_tree_root_dir):
    """
    State tree with files to test salt-ssh
    when the map.jinja file is in another directory
    """
    top_file = """
    {%- from "test/map.jinja" import abc with context %}
    base:
      'localhost':
        - test
      '127.0.0.1':
        - test
    """
    map_file = """
    {%- set abc = "def" %}
    """
    state_file = """
    {%- from "test/map.jinja" import abc with context %}

    Ok with {{ abc }}:
      test.succeed_without_changes
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    map_tempfile = pytest.helpers.temp_file(
        "test/map.jinja", map_file, base_env_state_tree_root_dir
    )
    state_tempfile = pytest.helpers.temp_file(
        "test.sls", state_file, base_env_state_tree_root_dir
    )

    with top_tempfile, map_tempfile, state_tempfile:
        yield
