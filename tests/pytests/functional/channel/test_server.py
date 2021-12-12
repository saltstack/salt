import logging
import os
import time

import pytest
import salt.channel.client
import salt.channel.server
import salt.config
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.utils.files
import salt.utils.process
from saltfactories.utils.ports import get_unused_localhost_port

log = logging.getLogger(__name__)


@pytest.fixture
def master_config(tmp_path):
    master_conf = salt.config.master_config("")
    master_conf["id"] = "master"
    master_conf["root_dir"] = str(tmp_path)
    master_conf["sock_dir"] = str(tmp_path)
    master_conf["interface"] = "127.0.0.1"
    master_conf["publish_port"] = get_unused_localhost_port()
    master_conf["ret_port"] = get_unused_localhost_port()
    master_conf["pki_dir"] = str(tmp_path / "pki")
    os.makedirs(master_conf["pki_dir"])
    salt.crypt.gen_keys(master_conf["pki_dir"], "master", 4096)
    minions_keys = os.path.join(master_conf["pki_dir"], "minions")
    os.makedirs(minions_keys)
    yield master_conf


@pytest.fixture
def configs(master_config):
    minion_conf = salt.config.minion_config("")
    minion_conf["root_dir"] = master_config["root_dir"]
    minion_conf["id"] = "minion"
    minion_conf["sock_dir"] = master_config["sock_dir"]
    minion_conf["ret_port"] = master_config["ret_port"]
    minion_conf["interface"] = "127.0.0.1"
    minion_conf["pki_dir"] = os.path.join(master_config["root_dir"], "pki_minion")
    os.makedirs(minion_conf["pki_dir"])
    minion_conf["master_port"] = master_config["ret_port"]
    minion_conf["master_ip"] = "127.0.0.1"
    minion_conf["master_uri"] = "tcp://127.0.0.1:{}".format(master_config["ret_port"])
    salt.crypt.gen_keys(minion_conf["pki_dir"], "minion", 4096)
    minion_pub = os.path.join(minion_conf["pki_dir"], "minion.pub")
    pub_on_master = os.path.join(master_config["pki_dir"], "minions", "minion")
    with salt.utils.files.fopen(minion_pub, "r") as rfp:
        with salt.utils.files.fopen(pub_on_master, "w") as wfp:
            wfp.write(rfp.read())
    return (minion_conf, master_config)


@pytest.fixture
def process_manager():
    process_manager = salt.utils.process.ProcessManager()
    try:
        yield process_manager
    finally:
        process_manager.terminate()


def test_pub_server_channel_with_zmq_transport(io_loop, configs, process_manager):
    minion_conf, master_conf = configs

    server_channel = salt.channel.server.PubServerChannel.factory(
        master_conf,
    )
    server_channel.pre_fork(process_manager)
    req_server_channel = salt.channel.server.ReqServerChannel.factory(master_conf)
    req_server_channel.pre_fork(process_manager)

    def handle_payload(payload):
        log.info("TEST - Req Server handle payload %r", payload)

    req_server_channel.post_fork(handle_payload, io_loop=io_loop)

    pub_channel = salt.channel.client.AsyncPubChannel.factory(minion_conf)
    received = []

    @salt.ext.tornado.gen.coroutine
    def doit(channel, server, received, timeout=60):
        log.info("TEST - BEFORE CHANNEL CONNECT")
        yield channel.connect()
        log.info("TEST - AFTER CHANNEL CONNECT")

        def cb(payload):
            log.info("TEST - PUB SERVER MSG %r", payload)
            received.append(payload)
            io_loop.stop()

        channel.on_recv(cb)
        server.publish({"tgt_type": "glob", "tgt": ["carbon"], "WTF": "SON"})
        start = time.time()
        while time.time() - start < timeout:
            yield salt.ext.tornado.gen.sleep(1)
        io_loop.stop()

    try:
        io_loop.add_callback(doit, pub_channel, server_channel, received)
        io_loop.start()
        assert len(received) == 1
    finally:
        server_channel.close()
        req_server_channel.close()
        pub_channel.close()


def test_pub_server_channel_with_tcp_transport(io_loop, configs, process_manager):
    minion_conf, master_conf = configs
    minion_conf["transport"] = "tcp"
    master_conf["transport"] = "tcp"

    server_channel = salt.channel.server.PubServerChannel.factory(
        master_conf,
    )
    server_channel.pre_fork(process_manager)
    req_server_channel = salt.channel.server.ReqServerChannel.factory(master_conf)
    req_server_channel.pre_fork(process_manager)

    def handle_payload(payload):
        log.info("TEST - Req Server handle payload %r", payload)

    req_server_channel.post_fork(handle_payload, io_loop=io_loop)

    pub_channel = salt.channel.client.AsyncPubChannel.factory(minion_conf)
    received = []

    @salt.ext.tornado.gen.coroutine
    def doit(channel, server, received, timeout=60):
        log.info("TEST - BEFORE CHANNEL CONNECT")
        yield channel.connect()
        log.info("TEST - AFTER CHANNEL CONNECT")

        def cb(payload):
            log.info("TEST - PUB SERVER MSG %r", payload)
            received.append(payload)
            io_loop.stop()

        channel.on_recv(cb)
        server.publish({"tgt_type": "glob", "tgt": ["minion"], "WTF": "SON"})
        start = time.time()
        while time.time() - start < timeout:
            yield salt.ext.tornado.gen.sleep(1)
        io_loop.stop()

    try:
        io_loop.add_callback(doit, pub_channel, server_channel, received)
        io_loop.start()
        assert len(received) == 1
    finally:
        server_channel.close()
        req_server_channel.close()
        pub_channel.close()
