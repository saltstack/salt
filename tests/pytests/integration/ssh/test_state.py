import json

import pytest

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


@pytest.fixture(scope="module")
def state_tree(base_env_state_tree_root_dir):
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
    state_file = """
    {%- from "map.jinja" import abc with context %}

    Ok with {{ abc }}:
      test.succeed_without_changes
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


@pytest.mark.slow_test
def test_state_with_import(salt_ssh_cli, state_tree):
    """
    verify salt-ssh can use imported map files in states
    """
    ret = salt_ssh_cli.run("state.sls", "test")
    assert ret.returncode == 0
    assert ret.data


@pytest.fixture
def nested_state_tree(base_env_state_tree_root_dir, tmp_path):
    top_file = """
    base:
      'localhost':
        - basic
      '127.0.0.1':
        - basic
    """
    state_file = """
    /{}/file.txt:
      file.managed:
        - source: salt://foo/file.jinja
        - template: jinja
    """.format(
        tmp_path
    )
    file_jinja = """
    {% from 'foo/map.jinja' import comment %}{{ comment }}
    """
    map_file = """
    {% set comment = "blah blah" %}
    """
    statedir = base_env_state_tree_root_dir / "foo"
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    map_tempfile = pytest.helpers.temp_file("map.jinja", map_file, statedir)
    file_tempfile = pytest.helpers.temp_file("file.jinja", file_jinja, statedir)
    state_tempfile = pytest.helpers.temp_file("init.sls", state_file, statedir)

    with top_tempfile, map_tempfile, state_tempfile, file_tempfile:
        yield


@pytest.mark.slow_test
def test_state_with_import_from_dir(salt_ssh_cli, nested_state_tree):
    """
    verify salt-ssh can use imported map files in states
    """
    ret = salt_ssh_cli.run(
        "--extra-filerefs=salt://foo/map.jinja", "state.apply", "foo"
    )
    assert ret.returncode == 0
    assert ret.data


@pytest.mark.slow_test
def test_state_low(salt_ssh_cli):
    """
    test state.low with salt-ssh
    """
    ret = salt_ssh_cli.run(
        "state.low", '{"state": "cmd", "fun": "run", "name": "echo blah"}'
    )
    assert (
        json.loads(ret.stdout)["localhost"]["cmd_|-echo blah_|-echo blah_|-run"][
            "changes"
        ]["stdout"]
        == "blah"
    )


@pytest.mark.slow_test
def test_state_high(salt_ssh_cli):
    """
    test state.high with salt-ssh
    """
    ret = salt_ssh_cli.run("state.high", '{"echo blah": {"cmd": ["run"]}}')
    assert (
        json.loads(ret.stdout)["localhost"]["cmd_|-echo blah_|-echo blah_|-run"][
            "changes"
        ]["stdout"]
        == "blah"
    )
