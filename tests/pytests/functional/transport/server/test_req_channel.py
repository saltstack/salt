import logging
import multiprocessing

import pytest
import salt.config
import salt.exceptions
import salt.ext.tornado.gen
import salt.log.setup
import salt.transport.client
import salt.transport.server
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
from saltfactories.utils.processes import terminate_process

log = logging.getLogger(__name__)


class ReqServerChannelProcess(salt.utils.process.SignalHandlingProcess):
    def __init__(self, config, req_channel_crypt):
        super().__init__()
        self._closing = False
        self.config = config
        self.req_channel_crypt = req_channel_crypt
        self.process_manager = salt.utils.process.ProcessManager(
            name="ReqServer-ProcessManager"
        )
        self.req_server_channel = salt.transport.server.ReqServerChannel.factory(
            self.config
        )
        self.req_server_channel.pre_fork(self.process_manager)
        self.io_loop = None
        self.running = multiprocessing.Event()

    def run(self):
        self.io_loop = salt.ext.tornado.ioloop.IOLoop()
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

    @salt.ext.tornado.gen.coroutine
    def _handle_payload(self, payload):
        if self.req_channel_crypt == "clear":
            raise salt.ext.tornado.gen.Return((payload, {"fun": "send_clear"}))
        raise salt.ext.tornado.gen.Return((payload, {"fun": "send"}))


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


def req_channel_crypt_ids(value):
    return "ReqChannel(crypt='{}')".format(value)


@pytest.fixture(params=["clear", "aes"], ids=req_channel_crypt_ids)
def req_channel_crypt(request):
    return request.param


@pytest.fixture
def req_channel(req_server_channel, salt_minion, req_channel_crypt):
    with salt.transport.client.ReqChannel.factory(
        salt_minion.config, crypt=req_channel_crypt
    ) as _req_channel:
        try:
            yield _req_channel
        finally:
            # Force termination of singleton
            _req_channel.obj._refcount = 0


def test_basic(req_channel):
    """
    Test a variety of messages, make sure we get the expected responses
    """
    msgs = [
        {"foo": "bar"},
        {"bar": "baz"},
        {"baz": "qux", "list": [1, 2, 3]},
    ]
    for msg in msgs:
        ret = req_channel.send(msg, timeout=5, tries=1)
        assert ret["load"] == msg


def test_normalization(req_channel):
    """
    Since we use msgpack, we need to test that list types are converted to lists
    """
    types = {
        "list": list,
    }
    msgs = [
        {"list": tuple([1, 2, 3])},
    ]
    for msg in msgs:
        ret = req_channel.send(msg, timeout=5, tries=1)
        for key, value in ret["load"].items():
            assert types[key] == type(value)


def test_badload(req_channel, req_channel_crypt):
    """
    Test a variety of bad requests, make sure that we get some sort of error
    """
    msgs = ["", [], tuple()]
    if req_channel_crypt == "clear":
        for msg in msgs:
            ret = req_channel.send(msg, timeout=5, tries=1)
            assert ret == "payload and load must be a dict"
    else:
        for msg in msgs:
            with pytest.raises(salt.exceptions.AuthenticationError):
                req_channel.send(msg, timeout=5, tries=1)
