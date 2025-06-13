import ctypes
import logging
import multiprocessing
import pathlib
import shutil
import time

import pytest
import tornado.gen
from pytestshellutils.utils.processes import terminate_process

import salt.channel.client
import salt.channel.server
import salt.config
import salt.crypt
import salt.exceptions
import salt.master
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.skip_on_spawning_platform(
        reason="These tests are currently broken on spawning platforms. Need to be rewritten.",
    ),
    pytest.mark.slow_test,
    pytest.mark.skipif(
        "grains['osfinger'] == 'Rocky Linux-8' and grains['osarch'] == 'aarch64'",
        reason="Temporarily skip on Rocky Linux 8 Arm64",
    ),
]


class ReqServerChannelProcess(salt.utils.process.SignalHandlingProcess):

    def __init__(self, config, req_channel_crypt):
        super().__init__()
        self._closing = False
        self.config = config
        self.req_channel_crypt = req_channel_crypt
        self.process_manager = salt.utils.process.ProcessManager(
            name="ReqServer-ProcessManager"
        )
        self.req_server_channel = salt.channel.server.ReqServerChannel.factory(
            self.config
        )
        self.req_server_channel.pre_fork(self.process_manager)
        self.io_loop = None
        self.running = multiprocessing.Event()

    def run(self):
        salt.master.SMaster.secrets["aes"] = {
            "secret": multiprocessing.Array(
                ctypes.c_char,
                salt.utils.stringutils.to_bytes(
                    salt.crypt.Crypticle.generate_key_string()
                ),
            ),
            "serial": multiprocessing.Value(
                ctypes.c_longlong, lock=False  # We'll use the lock from 'secret'
            ),
        }

        self.io_loop = tornado.ioloop.IOLoop()
        self.io_loop.make_current()
        self.req_server_channel.post_fork(self._handle_payload, io_loop=self.io_loop)
        self.io_loop.add_callback(self.running.set)
        try:
            self.io_loop.start()
        except KeyboardInterrupt:
            pass

    def _handle_signals(self, signum, sigframe):
        self.close()
        super()._handle_signals(signum, sigframe)

    def __enter__(self):
        self.start()
        self.running.wait()
        return self

    def __exit__(self, *args):
        self.close()
        self.terminate()

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self.req_server_channel is not None:
            self.req_server_channel.close()
            self.req_server_channel = None
        if self.process_manager is not None:
            self.process_manager.terminate()
            # Really terminate any process still left behind
            for pid in self.process_manager._process_map:
                terminate_process(pid=pid, kill_children=True, slow_stop=False)
            self.process_manager = None

    @tornado.gen.coroutine
    def _handle_payload(self, payload):
        if self.req_channel_crypt == "clear":
            raise tornado.gen.Return((payload, {"fun": "send_clear"}))
        for key in (
            "id",
            "ts",
            "tok",
        ):
            payload["load"].pop(key, None)
        raise tornado.gen.Return((payload, {"fun": "send"}))


@pytest.fixture
def req_server_channel(salt_master, req_channel_crypt):
    req_server_channel_process = ReqServerChannelProcess(
        salt_master.config.copy(), req_channel_crypt
    )
    try:
        with req_server_channel_process:
            yield
    finally:
        terminate_process(
            pid=req_server_channel_process.pid, kill_children=True, slow_stop=False
        )


@pytest.fixture
def req_server_opts(tmp_path):
    sock_dir = tmp_path / "sock"
    pki_dir = tmp_path / "pki"
    cache_dir = tmp_path / "cache"
    sock_dir.mkdir()
    pki_dir.mkdir()
    cache_dir.mkdir()
    yield {
        "sock_dir": sock_dir,
        "pki_dir": pki_dir,
        "cachedir": cache_dir,
        "key_pass": "meh",
        "keysize": 2048,
        "cluster_id": None,
        "master_sign_pubkey": False,
        "pub_server_niceness": None,
        "con_cache": False,
        "zmq_monitor": False,
        "request_server_ttl": 60,
        "publish_session": 600,
    }


@pytest.fixture
def req_server(req_server_opts):
    server = salt.channel.server.ReqServerChannel.factory(req_server_opts)
    try:
        yield server
    finally:
        server.close()


@pytest.fixture
def minion1_id():
    yield "minion1"


@pytest.fixture
def minion1_key(minion1_id, tmp_path, req_server_opts):
    minionpki = tmp_path / minion1_id
    minionpki.mkdir()
    key1 = pathlib.Path(salt.crypt.gen_keys(minionpki, minion1_id, 2048))

    pki = pathlib.Path(req_server_opts["pki_dir"])
    (pki / "minions").mkdir(exist_ok=True)
    shutil.copy2(key1.with_suffix(".pub"), pki / "minions" / minion1_id)
    yield salt.crypt.PrivateKey(key1)


@pytest.fixture
def minion2_id():
    yield "minion2"


@pytest.fixture
def minion2_key(minion2_id, tmp_path, req_server_opts):
    minionpki = tmp_path / minion2_id
    minionpki.mkdir()
    key2 = pathlib.Path(salt.crypt.gen_keys(minionpki, minion2_id, 2048))

    pki = pathlib.Path(req_server_opts["pki_dir"])
    (pki / "minions").mkdir(exist_ok=True)
    shutil.copy2(key2.with_suffix(".pub"), pki / "minions" / minion2_id)
    yield salt.crypt.PrivateKey(key2)


def req_channel_crypt_ids(value):
    return f"ReqChannel(crypt='{value}')"


@pytest.fixture(params=["clear", "aes"], ids=req_channel_crypt_ids)
def req_channel_crypt(request):
    return request.param


@pytest.fixture
def push_channel(req_server_channel, salt_minion, req_channel_crypt):
    with salt.channel.client.ReqChannel.factory(
        salt_minion.config, crypt=req_channel_crypt
    ) as _req_channel:
        try:
            yield _req_channel
        finally:
            # Force termination of singleton
            _req_channel.obj._refcount = 0


def test_basic(push_channel):
    """
    Test a variety of messages, make sure we get the expected responses
    """
    if push_channel.crypt == "aes":
        pytest.skip(reason="test not valid for encrypted channel")
    msgs = [
        {"foo": "bar"},
        {"bar": "baz"},
        {"baz": "qux", "list": [1, 2, 3]},
    ]
    for msg in msgs:
        ret = push_channel.send(dict(msg), timeout=5, tries=1)
        assert ret["load"] == msg


def test_normalization(push_channel):
    """
    Since we use msgpack, we need to test that list types are converted to lists
    """
    if push_channel.crypt == "aes":
        pytest.skip(reason="test not valid for encrypted channel")
    types = {
        "list": list,
    }
    msgs = [
        {"list": tuple([1, 2, 3])},
    ]
    for msg in msgs:
        ret = push_channel.send(msg, timeout=5, tries=1)
        for key, value in ret["load"].items():
            assert types[key] == type(value)


def test_badload(push_channel, req_channel_crypt):
    """
    Test a variety of bad requests, make sure that we get some sort of error
    """
    if push_channel.crypt == "aes":
        pytest.skip(reason="test not valid for encrypted channel")
    msgs = ["", [], tuple()]
    if req_channel_crypt == "clear":
        for msg in msgs:
            ret = push_channel.send(msg, timeout=5, tries=1)
            assert ret == "payload and load must be a dict"
    else:
        for msg in msgs:
            with pytest.raises(salt.exceptions.AuthenticationError):
                push_channel.send(msg, timeout=5, tries=1)


async def test_req_channel_ttl_v2(req_server, io_loop):
    req_server.opts["request_server_ttl"] = 60

    async def handler(payload):
        return payload, {"fun": "send"}

    req_server.post_fork(handler, io_loop)
    payload = {
        "enc": "aes",
        "version": 2,
        "load": req_server.crypticle.dumps(
            {
                "ts": int(time.time() - 61),
            }
        ),
    }
    ret = await req_server.handle_message(payload)
    ret = req_server.crypticle.loads(ret)
    assert ret == payload


async def test_req_channel_ttl_valid(req_server, io_loop, minion1_id, minion1_key):
    req_server.opts["request_server_ttl"] = 60
    req_server.opts["publish_session"] = 600
    tok = minion1_key.encrypt(b"salt")

    async def handler(payload):
        return payload, {"fun": "send"}

    req_server.post_fork(handler, io_loop)
    key = req_server.session_key(minion1_id)

    crypticle = salt.crypt.Crypticle(req_server.opts, key)
    payload = {
        "enc": "aes",
        "id": minion1_id,
        "version": 3,
        "load": crypticle.dumps(
            {
                "ts": int(time.time()),
                "id": minion1_id,
                "tok": tok,
            }
        ),
    }
    ret = await req_server.handle_message(payload)
    ret = crypticle.loads(ret)
    assert ret == payload


async def test_req_channel_ttl_expired(
    req_server, io_loop, caplog, minion1_id, minion1_key
):
    req_server.opts["request_server_ttl"] = 60
    req_server.opts["publish_session"] = 600
    tok = minion1_key.encrypt(b"salt")

    async def handler(payload):
        return payload, {"fun": "send"}

    req_server.post_fork(handler, io_loop)
    key = req_server.session_key(minion1_id)
    crypticle = salt.crypt.Crypticle(req_server.opts, key)
    payload = {
        "enc": "aes",
        "id": minion1_id,
        "version": 3,
        "load": crypticle.dumps(
            {
                "ts": int(time.time() - 61),
                "id": minion1_id,
                "tok": tok,
            }
        ),
    }
    with caplog.at_level(logging.WARNING):
        ret = await req_server.handle_message(payload)
        assert f"Received request from {minion1_id} with expired ttl" in caplog.text
        assert ret == "bad load"


async def test_req_channel_id_invalid_chars(
    req_server, minion1_id, minion1_key, io_loop, caplog
):
    req_server.opts["request_server_ttl"] = 60
    req_server.opts["publish_session"] = 600
    tok = minion1_key.encrypt(b"salt")

    async def handler(payload):
        return payload, {"fun": "send"}

    req_server.post_fork(handler, io_loop)
    key = req_server.session_key(minion1_id)
    crypticle = salt.crypt.Crypticle(req_server.opts, key)
    payload = {
        "enc": "aes",
        "id": f"{minion1_id}\0",
        "version": 3,
        "load": crypticle.dumps(
            {
                "ts": int(time.time()),
                "id": f"{minion1_id}\0",
                "tok": tok,
            }
        ),
    }
    with caplog.at_level(logging.WARNING):
        ret = await req_server.handle_message(payload)
        assert (
            "Bad load from minion: SaltDeserializationError: Encountered invalid id"
            in caplog.text
        )
        assert ret == "bad load"


async def test_req_channel_id_mismatch(
    req_server, io_loop, caplog, minion1_id, minion1_key
):

    id2 = "minion2"

    async def handler(payload):
        return payload, {"fun": "send"}

    req_server.post_fork(handler, io_loop)
    key = req_server.session_key(minion1_id)
    crypticle = salt.crypt.Crypticle(req_server.opts, key)
    payload = {
        "enc": "aes",
        "id": minion1_id,
        "version": 3,
        "load": crypticle.dumps(
            {
                "ts": int(time.time()),
                "id": id2,
            }
        ),
    }
    with caplog.at_level(logging.WARNING):
        ret = await req_server.handle_message(payload)
        assert (
            f"Request id mismatch. Found '{id2}' but expected '{minion1_id}'"
            in caplog.text
        )
        assert ret == "bad load"


async def test_req_channel_v2_invalid_token(
    req_server,
    io_loop,
    caplog,
    tmp_path,
    minion1_id,
    minion1_key,
    minion2_key,
    minion2_id,
):

    tok2 = minion2_key.encrypt(b"salt")

    async def handler(payload):
        return payload, {"fun": "send"}

    req_server.post_fork(handler, io_loop)

    # Minion 1 is trying to impersonate minion2's token.
    payload = {
        "enc": "aes",
        "version": 2,
        "load": req_server.crypticle.dumps(
            {
                "ts": int(time.time()),
                "id": minion1_id,
                "tok": tok2,
            }
        ),
    }
    with caplog.at_level(logging.WARNING):
        ret = await req_server.handle_message(payload)
        assert "Unable to decrypt token:" in caplog.text
        assert ret == "bad load"
