import pytest

pytestmark = [pytest.mark.slow_test]


def test_items(salt_ssh_cli):
    ret = salt_ssh_cli.run("config.items")
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert "id" in ret.data
    assert "grains" in ret.data
    assert "__master_opts__" in ret.data
    assert "cachedir" in ret.data


@pytest.mark.parametrize("omit", (False, True))
def test_option_minion_opt(salt_ssh_cli, omit):
    # Minion opt
    ret = salt_ssh_cli.run(
        "config.option", "id", omit_opts=omit, omit_grains=True, omit_master=True
    )
    assert ret.returncode == 0
    assert (ret.data != salt_ssh_cli.get_minion_tgt()) is omit
    assert (ret.data == "") is omit


# omit False not checked because cmd_yaml removed as a part of the great module migration.
@pytest.mark.parametrize("omit", (True,))
def test_option_pillar(salt_ssh_cli, omit):
    ret = salt_ssh_cli.run("config.option", "ext_spam", omit_pillar=omit)
    assert ret.returncode == 0
    assert (ret.data != "eggs") is omit
    assert (ret.data == "") is omit


@pytest.mark.parametrize("omit", (False, True))
def test_option_grain(salt_ssh_cli, omit):
    ret = salt_ssh_cli.run("config.option", "kernel", omit_grains=omit)
    assert ret.returncode == 0
    assert (
        ret.data not in ("Darwin", "Linux", "FreeBSD", "OpenBSD", "Windows")
    ) is omit
    assert (ret.data == "") is omit


@pytest.mark.parametrize("omit", (False, True))
def test_get_minion_opt(salt_ssh_cli, omit):
    ret = salt_ssh_cli.run("config.get", "cachedir", omit_master=True, omit_opts=omit)
    assert ret.returncode == 0
    assert (ret.data == "") is omit
    assert ("minion" not in ret.data) is omit


# omit False not checked because cmd_yaml removed as a part of the great module migration.
@pytest.mark.parametrize("omit", (True,))
def test_get_pillar(salt_ssh_cli, omit):
    ret = salt_ssh_cli.run("config.get", "ext_spam", omit_pillar=omit)
    assert ret.returncode == 0
    assert (ret.data != "eggs") is omit
    assert (ret.data == "") is omit


@pytest.mark.parametrize("omit", (False, True))
def test_get_grain(salt_ssh_cli, omit):
    ret = salt_ssh_cli.run("config.get", "kernel", omit_grains=omit)
    assert ret.returncode == 0
    assert (
        ret.data not in ("Darwin", "Linux", "FreeBSD", "OpenBSD", "Windows")
    ) is omit
    assert (ret.data == "") is omit
