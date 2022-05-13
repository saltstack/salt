"""
Tests for minion blackout
"""


import logging

import pytest

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.mark.slow_test
def test_blackout(salt_cli, blackout, salt_minion_1):
    """
    Test that basic minion blackout functionality works
    """
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json is True
    with blackout.enter_blackout("minion_blackout: true"):
        ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
        assert ret.exitcode == 1
        assert "Minion in blackout mode." in ret.stdout
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json is True


@pytest.mark.slow_test
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
    assert ret.exitcode == 0
    assert ret.json is True
    with blackout.enter_blackout(blackout_contents):
        ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
        assert ret.exitcode == 0
        assert ret.json is True

        ret = salt_cli.run("test.fib", "7", minion_tgt=salt_minion_1.id)
        assert ret.exitcode == 0
        assert ret.json[0] == 13


@pytest.mark.slow_test
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
    assert ret.exitcode == 0
    assert ret.json is True
    with blackout.enter_blackout(blackout_contents):
        ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
        assert ret.exitcode == 0
        assert ret.json is True

        ret = salt_cli.run("state.apply", minion_tgt=salt_minion_1.id)
        assert ret.exitcode == 1
        assert "Minion in blackout mode." in ret.stdout

        ret = salt_cli.run(
            "cloud.query", "list_nodes_full", minion_tgt=salt_minion_1.id
        )
        assert ret.exitcode == 1
        assert "Minion in blackout mode." in ret.stdout
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion_1.id)
    assert ret.exitcode == 0
    assert ret.json is True
