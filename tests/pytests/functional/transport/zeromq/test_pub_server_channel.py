import logging
import threading
import time

import pytest

import salt.transport.zeromq
from tests.support.mock import MagicMock, patch
from tests.support.pytest.transport import PubServerChannelProcess

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_on_fips_enabled_platform,
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


def test_pub_channel(master_opts):
    server = salt.transport.zeromq.PublishServer(master_opts)

    payloads = []

    def publish_payload(payload):
        server.publish_payload(payload)
        payloads.append(payload)

    thread = threading.Thread(target=server.publish_daemon, args=(publish_payload,))
    thread.start()

    server.publish({"meh": "bah"})

    start = time.monotonic()
    try:
        while not payloads:
            time.sleep(0.3)
            if time.monotonic() - start > 30:
                assert False, "No message received after 30 seconds"
    finally:
        server.close()
        server.io_loop.stop()
        thread.join()
        server.io_loop.close(all_fds=True)


def test_pub_channel_filtering(master_opts):
    master_opts["zmq_filtering"] = True
    server = salt.transport.zeromq.PublishServer(master_opts)

    payloads = []

    def publish_payload(payload):
        server.publish_payload(payload)
        payloads.append(payload)

    thread = threading.Thread(target=server.publish_daemon, args=(publish_payload,))
    thread.start()

    server.publish({"meh": "bah"})

    start = time.monotonic()
    try:
        while not payloads:
            time.sleep(0.3)
            if time.monotonic() - start > 30:
                assert False, "No message received after 30 seconds"
    finally:
        server.close()
        server.io_loop.stop()
        thread.join()
        server.io_loop.close(all_fds=True)


def test_pub_channel_filtering_topic(master_opts):
    master_opts["zmq_filtering"] = True
    server = salt.transport.zeromq.PublishServer(master_opts)

    payloads = []

    def publish_payload(payload):
        server.publish_payload(payload, topic_list=["meh"])
        payloads.append(payload)

    thread = threading.Thread(target=server.publish_daemon, args=(publish_payload,))
    thread.start()

    server.publish({"meh": "bah"})

    start = time.monotonic()
    try:
        while not payloads:
            time.sleep(0.3)
            if time.monotonic() - start > 30:
                assert False, "No message received after 30 seconds"
    finally:
        server.close()
        server.io_loop.stop()
        thread.join()
        server.io_loop.close(all_fds=True)
