import pytest

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module", autouse=True)
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


@pytest.fixture()
def pillar_filter_by_lookup():
    return {
        "common": {
            "has_common": True,
        },
        "custom_default": {
            "defaulted": True,
        },
        "merge": {
            "merged": True,
        },
    }


def test_pillar_items(salt_ssh_cli):
    """
    test pillar.items with salt-ssh
    """
    ret = salt_ssh_cli.run("pillar.items")
    assert ret.returncode == 0
    assert ret.data
    pillar_items = ret.data
    assert "monty" in pillar_items
    assert pillar_items["monty"] == "python"
    assert "knights" in pillar_items
    assert pillar_items["knights"] == ["Lancelot", "Galahad", "Bedevere", "Robin"]


def test_pillar_get(salt_ssh_cli):
    """
    test pillar.get with salt-ssh
    """
    ret = salt_ssh_cli.run("pillar.get", "monty")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data == "python"


def test_pillar_get_doesnotexist(salt_ssh_cli):
    """
    test pillar.get when pillar does not exist with salt-ssh
    """
    ret = salt_ssh_cli.run("pillar.get", "doesnotexist")
    assert ret.returncode == 0
    assert ret.data == ""


def test_pillar_filter_by(salt_ssh_cli, pillar_filter_by_lookup):
    """
    test pillar.filter_by with salt-ssh
    """
    pillar_filter_by_lookup["python"] = {"filtered": True}
    ret = salt_ssh_cli.run(
        "pillar.filter_by",
        pillar_filter_by_lookup,
        pillar="monty",
        merge=pillar_filter_by_lookup["merge"],
        base="common",
        default="custom_default",
    )
    assert ret.returncode == 0
    assert ret.data
    assert "has_common" in ret.data
    assert "filtered" in ret.data
    assert "merged" in ret.data
    assert "defaulted" not in ret.data


def test_pillar_filter_by_default(salt_ssh_cli, pillar_filter_by_lookup):
    """
    test pillar.filter_by default param with salt-ssh
    """
    ret = salt_ssh_cli.run(
        "pillar.filter_by",
        pillar_filter_by_lookup,
        pillar="monty",
        merge=pillar_filter_by_lookup["merge"],
        base="common",
        default="custom_default",
    )
    assert ret.returncode == 0
    assert ret.data
    assert "has_common" in ret.data
    assert "merged" in ret.data
    assert "defaulted" in ret.data
