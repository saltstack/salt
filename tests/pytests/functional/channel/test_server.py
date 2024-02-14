import asyncio
import ctypes
import logging
import multiprocessing
import os
import pathlib
import shutil
import stat
import time
from pathlib import Path

import pytest
from pytestshellutils.utils import ports
from saltfactories.utils import random_string

import salt.channel.client
import salt.channel.server
import salt.config
import salt.master
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason="These tests are currently broken on spawning platforms. Need to be rewritten.",
    ),
    pytest.mark.timeout_unless_on_windows(120),
]


@pytest.fixture
def channel_minion_id():
    return random_string("Tha-Minion-")


@pytest.fixture
def root_dir(tmp_path):
    if salt.utils.platform.is_darwin():
        # To avoid 'OSError: AF_UNIX path too long'
        _root_dir = pathlib.Path("/tmp").resolve() / tmp_path.name
        try:
            yield _root_dir
        finally:
            shutil.rmtree(str(_root_dir), ignore_errors=True)
    else:
        yield tmp_path


def transport_ids(value):
    return f"transport({value})"


# @pytest.fixture(params=["ws", "tcp", "zeromq"], ids=transport_ids)
@pytest.fixture(
    params=[
        "ws",
    ],
    ids=transport_ids,
)
def transport(request):
    return request.param


@pytest.fixture
def master_config(root_dir, transport):
    master_conf = salt.config.master_config("")
    master_conf["transport"] = transport
    master_conf["id"] = "master"
    master_conf["root_dir"] = str(root_dir)
    master_conf["sock_dir"] = str(root_dir)
    master_conf["interface"] = "127.0.0.1"
    master_conf["publish_port"] = ports.get_unused_localhost_port()
    master_conf["ret_port"] = ports.get_unused_localhost_port()
    master_conf["pki_dir"] = str(root_dir / "pki")
    os.makedirs(master_conf["pki_dir"])
    salt.crypt.gen_keys(master_conf["pki_dir"], "master", 4096)
    minions_keys = os.path.join(master_conf["pki_dir"], "minions")
    os.makedirs(minions_keys)
    yield master_conf


@pytest.fixture
def minion_config(master_config, channel_minion_id):
    minion_conf = salt.config.minion_config(
        "", minion_id=channel_minion_id, cache_minion_id=False
    )
    minion_conf["transport"] = master_config["transport"]
    minion_conf["root_dir"] = master_config["root_dir"]
    minion_conf["id"] = channel_minion_id
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
    pub_on_master = os.path.join(master_config["pki_dir"], "minions", channel_minion_id)
    shutil.copyfile(minion_pub, pub_on_master)
    return minion_conf


@pytest.fixture
def process_manager():
    process_manager = salt.utils.process.ProcessManager()
    try:
        yield process_manager
    finally:
        process_manager.terminate()


@pytest.fixture
def master_secrets():
    salt.master.SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "serial": multiprocessing.Value(
            ctypes.c_longlong, lock=False  # We'll use the lock from 'secret'
        ),
    }
    yield
    salt.master.SMaster.secrets.pop("aes")


async def _connect_and_publish(
    io_loop, channel_minion_id, channel, server, received, timeout=60
):
    await channel.connect()

    async def cb(payload):
        received.append(payload)
        io_loop.stop()

    channel.on_recv(cb)
    io_loop.spawn_callback(
        server.publish, {"tgt_type": "glob", "tgt": [channel_minion_id], "WTF": "SON"}
    )
    start = time.time()
    while time.time() - start < timeout:
        await asyncio.sleep(1)
    io_loop.stop()


def test_pub_server_channel(
    io_loop,
    channel_minion_id,
    master_config,
    minion_config,
    process_manager,
    master_secrets,
):
    server_channel = salt.channel.server.PubServerChannel.factory(
        master_config,
    )
    server_channel.pre_fork(process_manager)
    req_server_channel = salt.channel.server.ReqServerChannel.factory(master_config)
    req_server_channel.pre_fork(process_manager)

    async def handle_payload(payload):
        log.debug("Payload handler got %r", payload)

    req_server_channel.post_fork(handle_payload, io_loop=io_loop)

    if master_config["transport"] == "zeromq":
        p = Path(str(master_config["sock_dir"])) / "workers.ipc"
        start = time.time()
        while not p.exists():
            time.sleep(0.3)
            if time.time() - start > 20:
                raise Exception("IPC socket not created")
        mode = os.lstat(p).st_mode
        assert bool(os.lstat(p).st_mode & stat.S_IRUSR)
        assert not bool(os.lstat(p).st_mode & stat.S_IRGRP)
        assert not bool(os.lstat(p).st_mode & stat.S_IROTH)

    pub_channel = salt.channel.client.AsyncPubChannel.factory(
        minion_config, io_loop=io_loop
    )
    received = []

    try:
        io_loop.add_callback(
            _connect_and_publish,
            io_loop,
            channel_minion_id,
            pub_channel,
            server_channel,
            received,
        )
        io_loop.start()
        assert len(received) == 1
    finally:
        server_channel.close()
        req_server_channel.close()
        pub_channel.close()
