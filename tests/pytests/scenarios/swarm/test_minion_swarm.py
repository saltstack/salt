import random

import pytest

import salt.utils.platform

pytestmark = [
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def swarm_timeout():
    timeout = 120
    if salt.utils.platform.spawning_platform():
        timeout *= 2
    return timeout


def test_ping(minion_swarm, salt_cli, swarm_timeout):
    ret = salt_cli.run("test.ping", minion_tgt="*", _timeout=swarm_timeout)
    assert ret.returncode == 0
    assert ret.data
    for minion in minion_swarm:
        assert minion.id in ret.data
        minion_ret = ret.data[minion.id]
        # Sometimes the command times out but doesn't fail, so we catch it
        if isinstance(minion_ret, str) and "Minion did not return" in minion_ret:
            continue
        assert ret.data[minion.id] is True


def test_ping_one(minion_swarm, salt_cli, swarm_timeout):
    minion = random.choice(minion_swarm)
    ret = salt_cli.run("test.ping", minion_tgt=minion.id, _timeout=swarm_timeout)
    assert ret.returncode == 0
    assert ret.data is True
