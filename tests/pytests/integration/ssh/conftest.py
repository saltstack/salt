import pytest

from tests.support.helpers import system_python_version
from tests.support.pytest.helpers import reap_stray_processes


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
