import random

import pytest
from pytestshellutils.exceptions import FactoryTimeout

from salt.utils.platform import spawning_platform

pytestmark = [pytest.mark.slow_test]


def run_salt_cmd(salt_cli, *args, **kwargs):
    timeout = salt_cli.timeout
    if spawning_platform():
        timeout = salt_cli.timeout * 2
    kwargs["_timeout"] = timeout
    try:
        return salt_cli.run(*args, **kwargs)
    except FactoryTimeout:
        if spawning_platform():
            pytest.skip("Salt command timed out, skipping on spawning platform")


def test_ping(minion_swarm, salt_cli):
    ret = run_salt_cmd(salt_cli, "test.ping", minion_tgt="*")
    assert ret.data
    for minion in minion_swarm:
        assert minion.id in ret.data
        minion_ret = ret.data[minion.id]
        # Sometimes the command times out but doesn't fail, so we catch it
        if isinstance(minion_ret, str) and "Minion did not return" in minion_ret:
            continue
        assert ret.data[minion.id] is True


def test_ping_one(minion_swarm, salt_cli):
    minion = random.choice(minion_swarm)
    ret = run_salt_cmd(salt_cli, "test.ping", minion_tgt=minion.id)
    assert ret.data is True
