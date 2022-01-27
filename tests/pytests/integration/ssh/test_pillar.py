import pytest

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


@pytest.fixture(scope="module", autouse=True)
def module_pillar_tree(pillar_tree):
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
    top_tempfile = pillar_tree.base.temp_file("top.sls", top_file)
    basic_tempfile = pillar_tree.base.temp_file("basic.sls", basic_pillar_file)

    with top_tempfile, basic_tempfile:
        yield pillar_tree


@pytest.mark.slow_test
def test_pillar_items(salt_ssh_cli):
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
def test_pillar_get(salt_ssh_cli):
    """
    test pillar.get with salt-ssh
    """
    ret = salt_ssh_cli.run("pillar.get", "monty")
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == "python"


@pytest.mark.slow_test
def test_pillar_get_doesnotexist(salt_ssh_cli):
    """
    test pillar.get when pillar does not exist with salt-ssh
    """
    ret = salt_ssh_cli.run("pillar.get", "doesnotexist")
    assert ret.exitcode == 0
    assert ret.json == ""
