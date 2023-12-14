import shutil

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


@pytest.fixture(autouse=True)
def thin_dir(salt_ssh_cli):
    try:
        yield
    finally:
        ret = salt_ssh_cli.run("config.get", "thin_dir")
        assert ret.returncode == 0
        thin_dir_path = ret.data
        shutil.rmtree(thin_dir_path, ignore_errors=True)


def test_ssh_mine_get(salt_ssh_cli):
    """
    test salt-ssh with mine
    """
    ret = salt_ssh_cli.run("mine.get", "localhost", "test.arg")
    assert ret.returncode == 0
    assert ret.data
    assert "localhost" in ret.data
    assert "args" in ret.data["localhost"]
    assert ret.data["localhost"]["args"] == ["itworked"]


@pytest.mark.parametrize("tgts", (("ssh",), ("regular",), ("ssh", "regular")))
def test_mine_get(salt_ssh_cli, salt_minion, tgts):
    """
    Test mine returns with both regular and SSH minions
    """
    if len(tgts) > 1:
        tgt = "*"
        exp = {"localhost", salt_minion.id}
    else:
        tgt = "localhost" if "ssh" in tgts else salt_minion.id
        exp = {tgt}
    ret = salt_ssh_cli.run(
        "mine.get",
        "*",
        "test.ping",
        ssh_minions="ssh" in tgts,
        regular_minions="regular" in tgts,
    )
    assert ret.returncode == 0
    assert ret.data
    assert set(ret.data) == exp
    for id_ in exp:
        assert ret.data[id_] is True
