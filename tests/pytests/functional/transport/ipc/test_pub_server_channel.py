import logging
import threading
import time
from concurrent.futures.thread import ThreadPoolExecutor

import pytest
from saltfactories.utils import random_string

import salt.channel.server
import salt.master
from tests.support.pytest.transport import PubServerChannelProcess

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_on_fips_enabled_platform,
    pytest.mark.skip_on_spawning_platform(
        reason="These tests are currently broken on spawning platforms. Need to be rewritten.",
    ),
    pytest.mark.skipif(
        "grains['osfinger'] == 'Rocky Linux-8' and grains['osarch'] == 'aarch64'",
        reason="Temporarily skip on Rocky Linux 8 Arm64",
    ),
]


@pytest.fixture(scope="module", params=["zeromq", "tcp"])
def transport(request):
    yield request.param


@pytest.fixture(scope="module")
def salt_master(salt_factories, transport):
    config_defaults = {
        "transport": transport,
        "auto_accept": True,
        "sign_pub_messages": False,
    }
    factory = salt_factories.salt_master_daemon(
        random_string("ipc-master-"), defaults=config_defaults
    )
    return factory


@pytest.fixture(scope="module")
def salt_minion(salt_master):
    config_defaults = {
        "transport": salt_master.config["transport"],
        "master_ip": "127.0.0.1",
        "master_port": salt_master.config["ret_port"],
        "auth_timeout": 5,
        "auth_tries": 1,
        "master_uri": "tcp://127.0.0.1:{}".format(salt_master.config["ret_port"]),
    }
    factory = salt_master.salt_minion_daemon(
        random_string("zeromq-minion-"), defaults=config_defaults
    )
    return factory


@pytest.mark.skip_on_windows
@pytest.mark.slow_test
def test_publish_to_pubserv_ipc(salt_master, salt_minion, transport):
    """
    Test sending 10K messags to ZeroMQPubServerChannel using IPC transport

    ZMQ's ipc transport not supported on Windows
    """

    opts = dict(
        salt_master.config.copy(),
        ipc_mode="ipc",
        pub_hwm=0,
        transport=transport,
    )
    minion_opts = dict(salt_minion.config.copy(), transport=transport)
    with PubServerChannelProcess(opts, minion_opts) as server_channel:
        send_num = 10000
        expect = []
        for idx in range(send_num):
            expect.append(idx)
            load = {"tgt_type": "glob", "tgt": "*", "jid": idx}
            server_channel.publish(load)
    results = server_channel.collector.results
    assert len(results) == send_num, "{} != {}, difference: {}".format(
        len(results), send_num, set(expect).difference(results)
    )


@pytest.mark.skip_on_freebsd
@pytest.mark.slow_test
def test_issue_36469_tcp(salt_master, salt_minion, transport):
    """
    Test sending both large and small messags to publisher using TCP

    https://github.com/saltstack/salt/issues/36469
    """
    #  if transport == "tcp":
    #      pytest.skip("Test not applicable to the ZeroMQ transport.")

    def _send_small(queue, finished_event, sid, num=10):
        try:
            for idx in range(num):
                load = {"tgt_type": "glob", "tgt": "*", "jid": f"{sid}-s{idx}"}
                queue.put(load)
        finally:
            finished_event.set()

    def _send_large(queue, finished_event, sid, num=10, size=250000 * 3):
        try:
            for idx in range(num):
                load = {
                    "tgt_type": "glob",
                    "tgt": "*",
                    "jid": f"{sid}-l{idx}",
                    "xdata": "0" * size,
                }
                queue.put(load)
        finally:
            finished_event.set()

    opts = dict(salt_master.config.copy(), ipc_mode="tcp", pub_hwm=0)
    send_num = 10 * 4
    expect = []
    with PubServerChannelProcess(opts, salt_minion.config.copy()) as server_channel:
        assert "aes" in salt.master.SMaster.secrets
        finished_events = [threading.Event() for _ in range(4)]
        with ThreadPoolExecutor(max_workers=4) as executor:
            executor.submit(_send_small, server_channel.queue, finished_events[0], 1)
            executor.submit(_send_large, server_channel.queue, finished_events[1], 2)
            executor.submit(_send_small, server_channel.queue, finished_events[2], 3)
            executor.submit(_send_large, server_channel.queue, finished_events[3], 4)
        expect.extend([f"{sid}-s{idx}" for sid in (1, 3) for idx in range(10)])
        expect.extend([f"{sid}-l{idx}" for sid in (2, 4) for idx in range(10)])

        # Wait for all expected publishes to be observed before leaving the context.
        expected_set = set(expect)
        # The overall test has a 90s timeout; cap the wait so we fail fast if
        # pubs are stuck but still allow slower builders a chance to flush.
        deadline = time.monotonic() + 45
        interval = 0.5
        missing = expected_set
        while time.monotonic() < deadline:
            received = set(server_channel.collector.results)
            missing = expected_set - received
            if not missing:
                break
            log.debug(
                "Collector waiting for publishes; received=%s missing=%s",
                len(received),
                list(sorted(missing))[:5],
            )
            time.sleep(interval)
        else:
            pytest.fail(
                "Collector timed out waiting for publishes: "
                f"received={len(received)} expected={len(expected_set)} "
                f"missing={list(sorted(missing))[:5]}"
            )
        for event in finished_events:
            if not event.wait(timeout=5):
                pytest.fail("Publisher thread did not signal completion")
    results = server_channel.collector.results
    assert len(results) == send_num, "{} != {}, difference: {}".format(
        len(results), send_num, set(expect).difference(results)
    )
