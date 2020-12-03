import pathlib

import pytest
from tests.support.helpers import slowTest

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def pillar_tree(base_env_pillar_tree_root_dir, salt_minion, salt_call_cli):
    top_file = """
    base:
      '{}':
        - basic
    """.format(
        salt_minion.id
    )
    basic_pillar_file = """
    monty: python
    os: {{ grains['os'] }}
    {% if grains['os'] == 'Fedora' %}
    class: redhat
    {% else %}
    class: other
    {% endif %}

    knights:
      - Lancelot
      - Galahad
      - Bedevere
      - Robin
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_pillar_tree_root_dir
    )
    basic_tempfile = pytest.helpers.temp_file(
        "basic.sls", basic_pillar_file, base_env_pillar_tree_root_dir
    )
    try:
        with top_tempfile, basic_tempfile:
            ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
            assert ret.exitcode == 0
            assert ret.json is True
            yield
    finally:
        # Refresh pillar again to cleaup the temp pillar
        ret = salt_call_cli.run("saltutil.refresh_pillar", wait=True)
        assert ret.exitcode == 0
        assert ret.json is True


@slowTest
def test_data(salt_call_cli, pillar_tree):
    """
    pillar.data
    """
    ret = salt_call_cli.run("grains.items")
    assert ret.exitcode == 0
    assert ret.json
    grains = ret.json
    ret = salt_call_cli.run("pillar.data")
    assert ret.exitcode == 0
    assert ret.json
    pillar = ret.json
    assert pillar["os"] == grains["os"]
    assert pillar["monty"] == "python"
    if grains["os"] == "Fedora":
        assert pillar["class"] == "redhat"
    else:
        assert pillar["class"] == "other"


@slowTest
def test_issue_5449_report_actual_file_roots_in_pillar(
    salt_call_cli, pillar_tree, base_env_state_tree_root_dir
):
    """
    pillar['master']['file_roots'] is overwritten by the master
    in order to use the fileclient interface to read the pillar
    files. We should restore the actual file_roots when we send
    the pillar back to the minion.
    """
    ret = salt_call_cli.run("pillar.data")
    assert ret.exitcode == 0
    assert ret.json
    file_roots = ret.json["master"]["file_roots"]["base"]
    assert pathlib.Path(base_env_state_tree_root_dir).resolve() in [
        pathlib.Path(p).resolve() for p in file_roots
    ]


@slowTest
def test_ext_cmd_yaml(salt_call_cli, pillar_tree):
    """
    pillar.data for ext_pillar cmd.yaml
    """
    ret = salt_call_cli.run("pillar.data")
    assert ret.exitcode == 0
    assert ret.json
    pillar = ret.json
    assert pillar["ext_spam"] == "eggs"


@slowTest
def test_issue_5951_actual_file_roots_in_opts(
    salt_call_cli, pillar_tree, base_env_state_tree_root_dir
):
    ret = salt_call_cli.run("pillar.data")
    assert ret.exitcode == 0
    assert ret.json
    pillar_data = ret.json
    file_roots = pillar_data["ext_pillar_opts"]["file_roots"]["base"]
    assert pathlib.Path(base_env_state_tree_root_dir).resolve() in [
        pathlib.Path(p).resolve() for p in file_roots
    ]


@slowTest
def test_pillar_items(salt_call_cli, pillar_tree):
    """
    Test to ensure we get expected output
    from pillar.items
    """
    ret = salt_call_cli.run("pillar.items")
    assert ret.exitcode == 0
    assert ret.json
    pillar_items = ret.json
    assert "monty" in pillar_items
    assert pillar_items["monty"] == "python"
    assert "knights" in pillar_items
    assert pillar_items["knights"] == ["Lancelot", "Galahad", "Bedevere", "Robin"]


@slowTest
def test_pillar_command_line(salt_call_cli, pillar_tree):
    """
    Test to ensure when using pillar override
    on command line works
    """
    # test when pillar is overwriting previous pillar
    ret = salt_call_cli.run("pillar.items", pillar={"monty": "overwrite"})
    assert ret.exitcode == 0
    assert ret.json
    pillar_items = ret.json
    assert "monty" in pillar_items
    assert pillar_items["monty"] == "overwrite"

    # test when using additional pillar
    ret = salt_call_cli.run("pillar.items", pillar={"new": "additional"})
    assert ret.exitcode == 0
    assert ret.json
    pillar_items = ret.json
    assert "new" in pillar_items
    assert pillar_items["new"] == "additional"
