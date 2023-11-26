import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]


def test_salt_minion_ping(salt_cli, salt_minion):
    """
    Test running a command against a targeted minion
    """
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert ret.data is True


def test_salt_minion_setproctitle(salt_cli, salt_minion):
    """
    Test that setproctitle is working
    for the running Salt minion
    """
    ret = salt_cli.run(
        "ps.pgrep", "MinionProcessManager", full=True, minion_tgt=salt_minion.id
    )
    assert ret.returncode == 0
    assert ret.data != ""
