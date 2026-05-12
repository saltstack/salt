import pytest

import salt.modules.cmdmod as cmdmod
from salt.exceptions import CommandExecutionError

pytestmark = [pytest.mark.windows_whitelisted]


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
def test_runas(account):
    ret = cmdmod.run("id", runas=account.username)
    assert f"gid={account.info.gid}" in ret
    assert f"uid={account.info.uid}" in ret


def test_runas_missing_user():
    with pytest.raises(CommandExecutionError):
        cmdmod.run("echo HOLO", runas="non-existent-user", password="junk")
