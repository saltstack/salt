import copy
import logging
import random
import threading
import time
from contextlib import contextmanager

import pytest
from saltfactories.utils import random_string

import salt.transport.zeromq
import salt.utils.process
from tests.support.mock import MagicMock, patch
from tests.support.pytest.transport import PubServerChannelProcess

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_on_fips_enabled_platform,
    pytest.mark.skip_on_freebsd(reason="Temporarily skipped on FreeBSD."),
    pytest.mark.skip_on_spawning_platform(
        reason="These tests are currently broken on spawning platforms. Need to be rewritten.",
    ),
    pytest.mark.skipif(
        "grains['osfinger'] == 'Rocky Linux-8' and grains['osarch'] == 'aarch64'",
        reason="Temporarily skip on Rocky Linux 8 Arm64",
    ),
]


class PubServerChannelSender:
    def __init__(self, pub_server_channel, payload_list):
        self.pub_server_channel = pub_server_channel
        self.payload_list = payload_list

    def run(self):
        for payload in self.payload_list:
            self.pub_server_channel.publish(payload)
        time.sleep(2)


def generate_msg_list(msg_cnt, minions_list, broadcast):
    msg_list = []
    for i in range(msg_cnt):
        for idx, minion_id in enumerate(minions_list):
            if broadcast:
                msg_list.append(
                    {"tgt_type": "grain", "tgt": "id:*", "jid": msg_cnt * idx + i}
                )
            else:
                msg_list.append(
                    {"tgt_type": "list", "tgt": [minion_id], "jid": msg_cnt * idx + i}
                )
    return msg_list


@contextmanager
def channel_publisher_manager(msg_list, p_cnt, pub_server_channel):
    process_list = []
    msg_list = copy.deepcopy(msg_list)
    random.shuffle(msg_list)
    batch_size = len(msg_list) // p_cnt
    list_batch = [
        [x * batch_size, x * batch_size + batch_size] for x in range(0, p_cnt)
    ]
    list_batch[-1][1] = list_batch[-1][1] + 1
    try:
        for i, j in list_batch:
            c = PubServerChannelSender(pub_server_channel, msg_list[i:j])
            p = salt.utils.process.Process(target=c.run)
            process_list.append(p)
        for p in process_list:
            p.start()
        yield
    finally:
        for p in process_list:
            p.join()


@pytest.mark.skip_on_windows
@pytest.mark.slow_test
def test_zeromq_filtering_minion(salt_master, salt_minion):
    opts = dict(
        salt_master.config.copy(),
        ipc_mode="ipc",
        pub_hwm=0,
        zmq_filtering=True,
        acceptance_wait_time=5,
    )
    minion_opts = dict(
        salt_minion.config.copy(),
        zmq_filtering=True,
    )
    messages = 200
    workers = 5
    minions = 3
    expect = set(range(messages))
    target_minion_id = salt_minion.id
    minions_list = [target_minion_id]
    for _ in range(minions - 1):
        minions_list.append(random_string("zeromq-minion-"))
    msg_list = generate_msg_list(messages, minions_list, False)
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(
            return_value={
                "minions": minions_list,
                "missing": [],
                "ssh_minions": False,
            }
        ),
    ):
        with PubServerChannelProcess(opts, minion_opts) as server_channel:
            with channel_publisher_manager(
                msg_list, workers, server_channel.pub_server_channel
            ):
                cnt = 0
                last_results_len = 0
                while cnt < 20:
                    time.sleep(2)
                    results_len = len(server_channel.collector.results)
                    if last_results_len == results_len:
                        break
                    last_results_len = results_len
                    cnt += 1
        results = set(server_channel.collector.results)
        assert (
            results == expect
        ), f"{len(results)}, != {len(expect)}, difference: {expect.difference(results)} {results}"


@pytest.mark.skip_on_windows
@pytest.mark.slow_test
def test_zeromq_filtering_syndic(salt_master, salt_minion):
    opts = dict(
        salt_master.config.copy(),
        ipc_mode="ipc",
        pub_hwm=0,
        zmq_filtering=True,
        acceptance_wait_time=5,
        order_masters=True,
    )
    minion_opts = dict(
        salt_minion.config.copy(),
        zmq_filtering=True,
        __role="syndic",
    )
    messages = 200
    workers = 5
    minions = 3
    expect = set(range(messages * minions))
    minions_list = []
    for _ in range(minions):
        minions_list.append(random_string("zeromq-minion-"))
    msg_list = generate_msg_list(messages, minions_list, False)
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(
            return_value={
                "minions": minions_list,
                "missing": [],
                "ssh_minions": False,
            }
        ),
    ):
        with PubServerChannelProcess(opts, minion_opts) as server_channel:
            with channel_publisher_manager(
                msg_list, workers, server_channel.pub_server_channel
            ):
                cnt = 0
                last_results_len = 0
                while cnt < 20:
                    time.sleep(2)
                    results_len = len(server_channel.collector.results)
                    if last_results_len == results_len:
                        break
                    last_results_len = results_len
                    cnt += 1
        results = set(server_channel.collector.results)
        assert (
            results == expect
        ), f"{len(results)}, != {len(expect)}, difference: {expect.difference(results)} {results}"


@pytest.mark.skip_on_windows
@pytest.mark.slow_test
def test_zeromq_filtering_broadcast(salt_master, salt_minion):
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
    minion_opts = dict(
        salt_minion.config.copy(),
        zmq_filtering=True,
    )
    messages = 200
    workers = 5
    minions = 3
    expect = set(range(messages * minions))
    target_minion_id = salt_minion.id
    minions_list = [target_minion_id]
    for _ in range(minions - 1):
        minions_list.append(random_string("zeromq-minion-"))
    msg_list = generate_msg_list(messages, minions_list, True)
    with patch(
        "salt.utils.minions.CkMinions.check_minions",
        MagicMock(
            return_value={
                "minions": minions_list,
                "missing": [],
                "ssh_minions": False,
            }
        ),
    ):
        with PubServerChannelProcess(opts, minion_opts) as server_channel:
            with channel_publisher_manager(
                msg_list, workers, server_channel.pub_server_channel
            ):
                cnt = 0
                last_results_len = 0
                while cnt < 20:
                    time.sleep(2)
                    results_len = len(server_channel.collector.results)
                    if last_results_len == results_len:
                        break
                    last_results_len = results_len
                    cnt += 1
        results = set(server_channel.collector.results)
        assert (
            results == expect
        ), f"{len(results)}, != {len(expect)}, difference: {expect.difference(results)} {results}"


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
