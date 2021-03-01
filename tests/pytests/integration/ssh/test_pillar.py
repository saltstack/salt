import pytest

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


@pytest.fixture(scope="module")
def pillar_tree(base_env_pillar_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - basic
      '127.0.0.1':
        - basic
    """
    basic_pillar_file = """
    monty: python
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

    with top_tempfile, basic_tempfile:
        yield


@pytest.mark.slow_test
def test_pillar_items(salt_ssh_cli, pillar_tree):
    """
    test pillar.items with salt-ssh
    """
    ret = salt_ssh_cli.run("pillar.items")
    assert ret.exitcode == 0
    assert ret.json
    pillar_items = ret.json
    assert "monty" in pillar_items
    assert pillar_items["monty"] == "python"
    assert "knights" in pillar_items
    assert pillar_items["knights"] == ["Lancelot", "Galahad", "Bedevere", "Robin"]


@pytest.mark.slow_test
def test_pillar_get(salt_ssh_cli, pillar_tree):
    """
    test pillar.get with salt-ssh
    """
    ret = salt_ssh_cli.run("pillar.get", "monty")
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == "python"


@pytest.mark.slow_test
def test_pillar_get_doesnotexist(salt_ssh_cli, pillar_tree):
    """
    test pillar.get when pillar does not exist with salt-ssh
    """
    ret = salt_ssh_cli.run("pillar.get", "doesnotexist")
    assert ret.exitcode == 0
    assert ret.json == ""
