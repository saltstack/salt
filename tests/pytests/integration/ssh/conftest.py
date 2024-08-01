import pytest

from tests.support.pytest.helpers import reap_stray_processes


@pytest.fixture(scope="package", autouse=True)
def _auto_skip_on_system_python_too_recent(grains):
    if (
        grains["osfinger"] in ("Fedora Linux-40", "Ubuntu-24.04")
        or grains["os_family"] == "Arch"
    ):
        pytest.skip(
            "System ships with a version of python that is too recent for salt-ssh tests",
            # Actually, the problem is that the tornado we ship is not prepared for Python 3.12,
            # and it imports `ssl` and checks if the `match_hostname` function is defined, which
            # has been deprecated since Python 3.7, so, the logic goes into trying to import
            # backports.ssl-match-hostname which is not installed on the system.
        )


@pytest.fixture(autouse=True)
def _reap_stray_processes():
    # when tests timeout, we migth leave child processes behind
    # nuke them
    with reap_stray_processes():
        # Run test
        yield


@pytest.fixture(scope="module")
def state_tree(base_env_state_tree_root_dir):
    top_file = """
    {%- from "map.jinja" import abc with context %}
    base:
      'localhost':
        - basic
      '127.0.0.1':
        - basic
    """
    map_file = """
    {%- set abc = "def" %}
    """
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
