import logging
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


@pytest.fixture(scope="module", params=["tcp", "zeromq"])
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
    if transport == "tcp":
        pytest.skip("Test not applicable to the ZeroMQ transport.")

    def _send_small(opts, sid, num=10):
        server_channel = salt.channel.server.PubServerChannel.factory(opts)
        for idx in range(num):
            load = {"tgt_type": "glob", "tgt": "*", "jid": f"{sid}-s{idx}"}
            server_channel.publish(load)
        time.sleep(0.3)
        time.sleep(3)
        server_channel.close_pub()

    def _send_large(opts, sid, num=10, size=250000 * 3):
        server_channel = salt.channel.server.PubServerChannel.factory(opts)
        for idx in range(num):
            load = {
                "tgt_type": "glob",
                "tgt": "*",
                "jid": f"{sid}-l{idx}",
                "xdata": "0" * size,
            }
            server_channel.publish(load)
        time.sleep(0.3)
        server_channel.close_pub()

    opts = dict(salt_master.config.copy(), ipc_mode="tcp", pub_hwm=0)
    send_num = 10 * 4
    expect = []
    with PubServerChannelProcess(opts, salt_minion.config.copy()) as server_channel:
        assert "aes" in salt.master.SMaster.secrets
        with ThreadPoolExecutor(max_workers=4) as executor:
            executor.submit(_send_small, opts, 1)
            executor.submit(_send_large, opts, 2)
            executor.submit(_send_small, opts, 3)
            executor.submit(_send_large, opts, 4)
        expect.extend([f"{a}-s{b}" for a in range(10) for b in (1, 3)])
        expect.extend([f"{a}-l{b}" for a in range(10) for b in (2, 4)])
    results = server_channel.collector.results
    assert len(results) == send_num, "{} != {}, difference: {}".format(
        len(results), send_num, set(expect).difference(results)
    )
