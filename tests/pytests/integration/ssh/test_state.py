import json

import pytest

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


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


@pytest.mark.slow_test
def test_state_with_import(salt_ssh_cli, state_tree):
    """
    verify salt-ssh can use imported map files in states
    """
    ret = salt_ssh_cli.run("state.sls", "test")
    assert ret.returncode == 0
    assert ret.data


@pytest.mark.parametrize(
    "ssh_cmd",
    [
        "state.sls",
        "state.highstate",
        "state.apply",
        "state.show_top",
        "state.show_highstate",
        "state.show_low_sls",
        "state.show_lowstate",
        "state.sls_id",
        "state.show_sls",
        "state.top",
    ],
)
@pytest.mark.slow_test
def test_state_with_import_dir(salt_ssh_cli, state_tree_dir, ssh_cmd):
    """
    verify salt-ssh can use imported map files in states
    when the map files are in another directory outside of
    sls files importing them.
    """
    if ssh_cmd in ("state.sls", "state.show_low_sls", "state.show_sls"):
        ret = salt_ssh_cli.run("-w", "-t", ssh_cmd, "test")
    elif ssh_cmd == "state.top":
        ret = salt_ssh_cli.run("-w", "-t", ssh_cmd, "top.sls")
    elif ssh_cmd == "state.sls_id":
        ret = salt_ssh_cli.run("-w", "-t", ssh_cmd, "Ok with def", "test")
    else:
        ret = salt_ssh_cli.run("-w", "-t", ssh_cmd)
    assert ret.returncode == 0
    if ssh_cmd == "state.show_top":
        assert ret.data == {"base": ["test", "master_tops_test"]} or {"base": ["test"]}
    elif ssh_cmd in ("state.show_highstate", "state.show_sls"):
        assert ret.data == {
            "Ok with def": {
                "__sls__": "test",
                "__env__": "base",
                "test": ["succeed_without_changes", {"order": 10000}],
            }
        }
    elif ssh_cmd in ("state.show_low_sls", "state.show_lowstate", "state.show_sls"):
        assert ret.data == [
            {
                "state": "test",
                "name": "Ok with def",
                "__sls__": "test",
                "__env__": "base",
                "__id__": "Ok with def",
                "order": 10000,
                "fun": "succeed_without_changes",
            }
        ]
    else:
        assert ret.data["test_|-Ok with def_|-Ok with def_|-succeed_without_changes"][
            "result"
        ]
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
