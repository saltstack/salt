"""
Tests for minion blackout
"""

import logging

import pytest

log = logging.getLogger(__name__)


def _check_skip(grains):
    """
    Skip on windows because these tests are flaky, we need to spend some time to
    debug why.
    """
    if grains["os"] == "Windows":
        return True
    return False


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_initial_gh_actions_failure(skip=_check_skip),
]


def test_blackout(salt_cli, blackout, salt_minion_1):
    """
    Test that basic minion blackout functionality works
    """
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
    assert ret.returncode == 0
    assert ret.data is True
    with blackout.enter_blackout("minion_blackout: true"):
        ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
        assert ret.returncode == 1
        assert "Minion in blackout mode." in ret.stdout
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
    assert ret.returncode == 0
    assert ret.data is True


def test_blackout_whitelist(salt_cli, blackout, salt_minion_1):
    """
    Test that minion blackout whitelist works
    """
    blackout_contents = """
    minion_blackout: True
    minion_blackout_whitelist:
      - test.ping
      - test.fib
    """
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
    assert ret.returncode == 0
    assert ret.data is True
    with blackout.enter_blackout(blackout_contents):
        ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
        assert ret.returncode == 0
        assert ret.data is True

        ret = salt_cli.run("test.fib", "7", minion_tgt=salt_minion_1.id)
        assert ret.returncode == 0
        assert ret.data[0] == 13


def test_blackout_nonwhitelist(salt_cli, blackout, salt_minion_1):
    """
    Test that minion refuses to run non-whitelisted functions during
    blackout whitelist
    """
    blackout_contents = """
    minion_blackout: True
    minion_blackout_whitelist:
      - test.ping
      - test.fib
    """
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
    assert ret.returncode == 0
    assert ret.data is True
    with blackout.enter_blackout(blackout_contents):
        ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
        assert ret.returncode == 0
        assert ret.data is True

        ret = salt_cli.run("state.apply", minion_tgt=salt_minion_1.id)
        assert ret.returncode == 1
        assert "Minion in blackout mode." in ret.stdout

        ret = salt_cli.run(
            "cloud.query", "list_nodes_full", minion_tgt=salt_minion_1.id
        )
        assert ret.returncode == 1
        assert "Minion in blackout mode." in ret.stdout
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
    assert ret.returncode == 0
    assert ret.data is True
