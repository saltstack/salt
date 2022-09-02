import random

import pytest

pytestmark = [pytest.mark.slow_test]


def test_ping(minion_swarm, salt_cli):
    ret = salt_cli.run("test.ping", minion_tgt="*")
    assert ret.data
    for minion in minion_swarm:
        assert minion.id in ret.data
        assert ret.data[minion.id] is True


def test_ping_one(minion_swarm, salt_cli):
    minion = random.choice(minion_swarm)
    ret = salt_cli.run("test.ping", minion_tgt=minion.id)
    assert ret.data is True
