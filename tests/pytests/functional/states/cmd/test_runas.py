import pytest


@pytest.fixture(scope="module")
def account():
    with pytest.helpers.create_account(create_group=True) as _account:
        yield _account


@pytest.mark.skip_on_windows
@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_runas_id(cmd, account):
    ret = cmd.run("id", runas=account.username)
    assert ret.result is True
    assert f"uid={account.info.uid}" in ret.changes["stdout"]
    assert f"gid={account.info.gid}" in ret.changes["stdout"]
