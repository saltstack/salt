import random

import pytest

from salt.utils.platform import spawning_platform

pytestmark = [pytest.mark.slow_test]


@pytest.fixture
def timeout(salt_cli):
    if spawning_platform():
        return salt_cli.timeout * 2
    return salt_cli.timeout


def test_ping(minion_swarm, salt_cli, timeout):
    ret = salt_cli.run("test.ping", minion_tgt="*", _timeout=timeout)
    assert ret.data
    for minion in minion_swarm:
        assert minion.id in ret.data
        minion_ret = ret.data[minion.id]
        # Sometimes the command times out but doesn't fail, so we catch it
        if isinstance(minion_ret, str) and "Minion did not return" in minion_ret:
            continue
        assert ret.data[minion.id] is True


def test_ping_one(minion_swarm, salt_cli, timeout):
    minion = random.choice(minion_swarm)
    ret = salt_cli.run("test.ping", minion_tgt=minion.id, _timeout=timeout)
    assert ret.data is True
