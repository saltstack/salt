import logging

import pytest

from tests.support.mock import MagicMock, patch
from tests.support.pytest.transport import PubServerChannelProcess

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_on_freebsd(reason="Temporarily skipped on FreeBSD."),
    pytest.mark.skip_on_spawning_platform(
        reason="These tests are currently broken on spawning platforms. Need to be rewritten.",
    ),
]


@pytest.mark.skip_on_windows
@pytest.mark.slow_test
def test_zeromq_filtering(salt_master, salt_minion):
    """
    Test sending messages to publisher using UDP with zeromq_filtering enabled
    """
    opts = dict(
        salt_master.config.copy(),
        ipc_mode="ipc",
        pub_hwm=0,
        zmq_filtering=True,
        acceptance_wait_time=5,
    )
    send_num = 1
    expect = []
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(
            return_value={
                "minions": [salt_minion.id],
                "missing": [],
                "ssh_minions": False,
            }
        ),
    ):
        with PubServerChannelProcess(
            opts, salt_minion.config.copy(), zmq_filtering=True
        ) as server_channel:
            expect.append(send_num)
            load = {"tgt_type": "glob", "tgt": "*", "jid": send_num}
            server_channel.publish(load)
        results = server_channel.collector.results
        assert len(results) == send_num, "{} != {}, difference: {}".format(
            len(results), send_num, set(expect).difference(results)
        )
