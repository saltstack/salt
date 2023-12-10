import pytest

import salt.modules.cmdmod as cmdmod


@pytest.fixture(scope="module")
def account():
    with pytest.helpers.create_account(create_group=True) as _account:
        yield _account


@pytest.fixture(scope="module")
def configure_loader_modules():
    return {
        cmdmod: {
            "__grains__": {"os": "linux", "os_family": "linux"},
        }
    }


@pytest.mark.skip_on_windows
@pytest.mark.skip_if_not_root
def test_run_as(account):
    ret = cmdmod.run("id", runas=account.username)
    assert "gid={}".format(account.info.gid) in ret
    assert "uid={}".format(account.info.uid) in ret
