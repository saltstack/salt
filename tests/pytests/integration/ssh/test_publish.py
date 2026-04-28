import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


@pytest.mark.parametrize("tgts", (("ssh",), ("regular",), ("ssh", "regular")))
def test_publish(salt_ssh_cli, salt_minion, tgts):
    if len(tgts) > 1:
        tgt = "*"
        exp = {"localhost", salt_minion.id}
    else:
        tgt = "localhost" if "ssh" in tgts else salt_minion.id
        exp = {tgt}
    ret = salt_ssh_cli.run(
        "publish.publish",
        tgt,
        "test.ping",
        ssh_minions="ssh" in tgts,
        regular_minions="regular" in tgts,
    )
    assert ret.returncode == 0
    assert ret.data
    assert set(ret.data) == exp
    for id_ in exp:
        assert ret.data[id_] is True


def test_publish_with_arg(salt_ssh_cli, salt_minion):
    ret = salt_ssh_cli.run(
        "publish.publish",
        "*",
        "test.kwarg",
        arg=["cheese=spam"],
        ssh_minions=True,
        regular_minions=True,
    )
    assert ret.returncode == 0
    assert ret.data
    exp = {salt_minion.id, "localhost"}
    assert set(ret.data) == exp
    for id_ in exp:
        assert ret.data[id_]["cheese"] == "spam"


def test_publish_with_yaml_args(salt_ssh_cli, salt_minion):
    args = ["saltines, si", "crackers, nein", "cheese, indeed"]
    test_args = f'["{args[0]}", "{args[1]}", "{args[2]}"]'
    ret = salt_ssh_cli.run(
        "publish.publish",
        "*",
        "test.arg",
        arg=test_args,
        ssh_minions=True,
        regular_minions=True,
    )
    assert ret.returncode == 0
    assert ret.data
    exp = {salt_minion.id, "localhost"}
    assert set(ret.data) == exp
    for id_ in exp:
        assert ret.data[id_]["args"] == args


@pytest.mark.parametrize("tgts", (("ssh",), ("regular",), ("ssh", "regular")))
def test_full_data(salt_ssh_cli, salt_minion, tgts):
    if len(tgts) > 1:
        tgt = "*"
        exp = {"localhost", salt_minion.id}
    else:
        tgt = "localhost" if "ssh" in tgts else salt_minion.id
        exp = {tgt}
    ret = salt_ssh_cli.run(
        "publish.full_data",
        tgt,
        "test.fib",
        arg=20,
        ssh_minions="ssh" in tgts,
        regular_minions="regular" in tgts,
    )
    assert ret.returncode == 0
    assert ret.data
    assert set(ret.data) == exp
    for id_ in exp:
        assert "ret" in ret.data[id_]
        assert ret.data[id_]["ret"][0] == 6765


def test_full_data_kwarg(salt_ssh_cli, salt_minion):
    ret = salt_ssh_cli.run(
        "publish.full_data",
        "*",
        "test.kwarg",
        arg=["cheese=spam"],
        ssh_minions=True,
        regular_minions=True,
    )
    assert ret.returncode == 0
    assert ret.data
    exp = {"localhost", salt_minion.id}
    assert set(ret.data) == exp
    for id_ in exp:
        assert "ret" in ret.data[id_]
        assert ret.data[id_]["ret"]["cheese"] == "spam"
