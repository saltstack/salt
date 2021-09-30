import ctypes
import io
import logging
import multiprocessing
import os
import threading
import time
from concurrent.futures.thread import ThreadPoolExecutor

import pytest
import salt.channel.client
import salt.channel.server
import salt.config
import salt.exceptions
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.log.setup
import salt.master
import salt.transport.client
import salt.transport.server
import salt.transport.zeromq
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
import zmq
from saltfactories.utils.ports import get_unused_localhost_port
from saltfactories.utils.processes import terminate_process
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def master_config(tmp_path):
    master_conf = salt.config.master_config("")
    master_conf["id"] = "master"
    master_conf["root_dir"] = str(tmp_path)
    master_conf["sock_dir"] = str(tmp_path)
    master_conf["ret_port"] = get_unused_localhost_port()
    master_conf["master_uri"] = "tcp://127.0.0.1:{}".format(master_conf["ret_port"])
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
    minion_conf["pki_dir"] = os.path.join(master_config["root_dir"], "pki_minion")
    os.makedirs(minion_conf["pki_dir"])
    minion_conf["master_port"] = master_config["ret_port"]
    minion_conf["master_ip"] = "127.0.0.1"
    minion_conf["master_uri"] = "tcp://127.0.0.1:{}".format(master_config["ret_port"])
    salt.crypt.gen_keys(minion_conf["pki_dir"], "minion", 4096)
    minion_pub = os.path.join(minion_conf["pki_dir"], "minion.pub")
    pub_on_master = os.path.join(master_config["pki_dir"], "minions", "minion")
    with io.open(minion_pub, "r") as rfp:
        with io.open(pub_on_master, "w") as wfp:
            wfp.write(rfp.read())
    return (minion_conf, master_config)


def test_pub_server_channel_with_zmq_transport(io_loop, configs):
    minion_conf, master_conf = configs

    process_manager = salt.utils.process.ProcessManager()
    server_channel = salt.transport.server.PubServerChannel.factory(
        master_conf,
    )
    server_channel.pre_fork(process_manager)
    req_server_channel = salt.transport.server.ReqServerChannel.factory(master_conf)
    req_server_channel.pre_fork(process_manager)

    def handle_payload(payload):
        log.info("TEST - Req Server handle payload {}".format(repr(payload)))

    req_server_channel.post_fork(handle_payload, io_loop=io_loop)

    pub_channel = salt.transport.client.AsyncPubChannel.factory(minion_conf)

    @salt.ext.tornado.gen.coroutine
    def doit(channel, server):
        log.info("TEST - BEFORE CHANNEL CONNECT")
        yield channel.connect()
        log.info("TEST - AFTER CHANNEL CONNECT")

        def cb(payload):
            log.info("TEST - PUB SERVER MSG {}".format(repr(payload)))
            io_loop.stop()

        channel.on_recv(cb)
        server.publish({"tgt_type": "glob", "tgt": ["carbon"], "WTF": "SON"})

    io_loop.add_callback(doit, pub_channel, server_channel)
    io_loop.start()
    #    server_channel.transport.stop()
    process_manager.terminate()


def test_pub_server_channel_with_tcp_transport(io_loop, configs):
    minion_conf, master_conf = configs
    minion_conf["transport"] = "tcp"
    master_conf["transport"] = "tcp"

    process_manager = salt.utils.process.ProcessManager()
    server_channel = salt.transport.server.PubServerChannel.factory(
        master_conf,
    )
    server_channel.pre_fork(process_manager)
    req_server_channel = salt.transport.server.ReqServerChannel.factory(master_conf)
    req_server_channel.pre_fork(process_manager)

    def handle_payload(payload):
        log.info("TEST - Req Server handle payload {}".format(repr(payload)))

    req_server_channel.post_fork(handle_payload, io_loop=io_loop)

    pub_channel = salt.transport.client.AsyncPubChannel.factory(minion_conf)

    @salt.ext.tornado.gen.coroutine
    def doit(channel, server):
        log.info("TEST - BEFORE CHANNEL CONNECT")
        yield channel.connect()
        log.info("TEST - AFTER CHANNEL CONNECT")

        def cb(payload):
            log.info("TEST - PUB SERVER MSG {}".format(repr(payload)))
            io_loop.stop()

        channel.on_recv(cb)
        server.publish({"tgt_type": "glob", "tgt": ["carbon"], "WTF": "SON"})

    io_loop.add_callback(doit, pub_channel, server_channel)
    io_loop.start()
    # server_channel.transport.stop()
    process_manager.terminate()
