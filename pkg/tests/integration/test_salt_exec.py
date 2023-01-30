from sys import platform

import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]


def test_salt_cmd_run(salt_cli, salt_minion):
    """
    Test salt cmd.run 'ipconfig' or 'ls -lah /'
    """
    ret = None
    if platform.startswith("win"):
        ret = salt_cli.run("cmd.run", "ipconfig", minion_tgt=salt_minion.id)
    else:
        ret = salt_cli.run("cmd.run", "ls -lah /", minion_tgt=salt_minion.id)
    assert ret
    assert ret.stdout


def test_salt_list_users(salt_cli, salt_minion):
    """
    Test salt user.list_users
    """
    ret = salt_cli.run("user.list_users", minion_tgt=salt_minion.id)
    if platform.startswith("win"):
        assert "Administrator" in ret.stdout
    else:
        assert "root" in ret.stdout
