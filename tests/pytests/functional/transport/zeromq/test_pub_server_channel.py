import ctypes
import logging
import multiprocessing
import socket
import time
from concurrent.futures.thread import ThreadPoolExecutor

import pytest
import salt.config
import salt.exceptions
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.log.setup
import salt.master
import salt.transport.client
import salt.transport.server
import salt.transport.tcp
import salt.transport.zeromq
import salt.utils.msgpack
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
import zmq.eventloop.ioloop
from saltfactories.utils.processes import terminate_process
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


class RecvError(Exception):
    """
    Raised by the Collector's _recv method when there is a problem
    getting publishes from to the publisher.
    """


class Collector(salt.utils.process.SignalHandlingProcess):
    def __init__(
        self, minion_config, interface, port, aes_key, timeout=30, zmq_filtering=False
    ):
        super().__init__()
        self.minion_config = minion_config
        self.interface = interface
        self.port = port
        self.aes_key = aes_key
        self.timeout = timeout
        self.hard_timeout = time.time() + timeout + 30
        self.manager = multiprocessing.Manager()
        self.results = self.manager.list()
        self.zmq_filtering = zmq_filtering
        self.stopped = multiprocessing.Event()
        self.started = multiprocessing.Event()
        self.running = multiprocessing.Event()
        if salt.utils.msgpack.version >= (0, 5, 2):
            # Under Py2 we still want raw to be set to True
            msgpack_kwargs = {"raw": False}
        else:
            msgpack_kwargs = {"encoding": "utf-8"}
        self.unpacker = salt.utils.msgpack.Unpacker(**msgpack_kwargs)

    @property
    def transport(self):
        return self.minion_config["transport"]

    def _rotate_secrets(self, now=None):
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
            "reload": salt.crypt.Crypticle.generate_key_string,
            "rotate_master_key": self._rotate_secrets,
        }

    def _setup_listener(self):
        if self.transport == "zeromq":
            ctx = zmq.Context()
            self.sock = ctx.socket(zmq.SUB)
            self.sock.setsockopt(zmq.LINGER, -1)
            self.sock.setsockopt(zmq.SUBSCRIBE, b"")
            pub_uri = "tcp://{}:{}".format(self.interface, self.port)
            self.sock.connect(pub_uri)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            end = time.time() + 60
            while True:
                try:
                    sock.connect((self.interface, self.port))
                except ConnectionRefusedError:
                    if time.time() >= end:
                        raise
                    time.sleep(1)
                else:
                    break
            self.sock = salt.ext.tornado.iostream.IOStream(sock)

    @salt.ext.tornado.gen.coroutine
    def _recv(self):
        if self.transport == "zeromq":
            # test_zeromq_filtering requires catching the
            # SaltDeserializationError in order to pass.
            try:
                payload = self.sock.recv(zmq.NOBLOCK)
                serial_payload = salt.payload.loads(payload)
                raise salt.ext.tornado.gen.Return(serial_payload)
            except (zmq.ZMQError, salt.exceptions.SaltDeserializationError):
                raise RecvError("ZMQ Error")
        else:
            for msg in self.unpacker:
                serial_payload = salt.payload.loads(msg["body"])
                raise salt.ext.tornado.gen.Return(serial_payload)
            byts = yield self.sock.read_bytes(8096, partial=True)
            self.unpacker.feed(byts)
            for msg in self.unpacker:
                serial_payload = salt.payload.loads(msg["body"])
                raise salt.ext.tornado.gen.Return(serial_payload)
            raise RecvError("TCP Error")

    @salt.ext.tornado.gen.coroutine
    def _run(self, loop):
        self._setup_listener()
        last_msg = time.time()
        crypticle = salt.crypt.Crypticle(self.minion_config, self.aes_key)
        self.started.set()
        while True:
            curr_time = time.time()
            if time.time() > self.hard_timeout:
                break
            if curr_time - last_msg >= self.timeout:
                break
            try:
                payload = yield self._recv()
            except RecvError:
                time.sleep(0.01)
            else:
                try:
                    payload = crypticle.loads(payload["load"])
                    if not payload:
                        continue
                    if "start" in payload:
                        self.running.set()
                        continue
                    if "stop" in payload:
                        break
                    last_msg = time.time()
                    self.results.append(payload["jid"])
                except salt.exceptions.SaltDeserializationError:
                    if not self.zmq_filtering:
                        log.exception("Failed to deserialize...")
                        break
        loop.stop()

    def run(self):
        """
        Gather results until then number of seconds specified by timeout passes
        without receiving a message
        """
        loop = salt.ext.tornado.ioloop.IOLoop()
        loop.add_callback(self._run, loop)
        loop.start()

    def __enter__(self):
        self.manager.__enter__()
        self.start()
        # Wait until we can start receiving events
        self.started.wait()
        self.started.clear()
        return self

    def __exit__(self, *args):
        # Wait until we either processed all expected messages or we reach the hard timeout
        join_secs = self.hard_timeout - time.time()
        log.info("Waiting at most %s seconds before exiting the collector", join_secs)
        self.join(join_secs)
        self.terminate()
        # Cast our manager.list into a plain list
        self.results = list(self.results)
        # Terminate our multiprocessing manager
        self.manager.__exit__(*args)
        log.debug("The collector has exited")
        self.stopped.set()


class PubServerChannelProcess(salt.utils.process.SignalHandlingProcess):
    def __init__(self, master_config, minion_config, **collector_kwargs):
        super().__init__()
        self._closing = False
        self.master_config = master_config
        self.minion_config = minion_config
        self.collector_kwargs = collector_kwargs
        self.aes_key = salt.crypt.Crypticle.generate_key_string()
        salt.master.SMaster.secrets["aes"] = {
            "secret": multiprocessing.Array(
                ctypes.c_char,
                salt.utils.stringutils.to_bytes(self.aes_key),
            ),
            "serial": multiprocessing.Value(
                ctypes.c_longlong, lock=False  # We'll use the lock from 'secret'
            ),
        }
        self.process_manager = salt.utils.process.ProcessManager(
            name="ZMQ-PubServer-ProcessManager"
        )
        self.pub_server_channel = salt.transport.server.PubServerChannel.factory(
            self.master_config
        )
        self.pub_server_channel.pre_fork(
            self.process_manager,
            kwargs={"log_queue": salt.log.setup.get_multiprocessing_logging_queue()},
        )
        self.queue = multiprocessing.Queue()
        self.stopped = multiprocessing.Event()
        self.collector = Collector(
            self.minion_config,
            self.master_config["interface"],
            self.master_config["publish_port"],
            self.aes_key,
            **self.collector_kwargs
        )

    def run(self):
        try:
            while True:
                payload = self.queue.get()
                if payload is None:
                    log.debug("We received the stop sentinel")
                    break
                self.pub_server_channel.publish(payload)
        except KeyboardInterrupt:
            pass
        finally:
            self.stopped.set()

    def _handle_signals(self, signum, sigframe):
        self.close()
        super()._handle_signals(signum, sigframe)

    def close(self):
        if self._closing:
            return
        self._closing = True
        if self.process_manager is None:
            return
        self.process_manager.terminate()
        if hasattr(self.pub_server_channel, "pub_close"):
            self.pub_server_channel.pub_close()
        # Really terminate any process still left behind
        for pid in self.process_manager._process_map:
            terminate_process(pid=pid, kill_children=True, slow_stop=False)
        self.process_manager = None

    def publish(self, payload):
        self.queue.put(payload)

    def __enter__(self):
        self.start()
        self.collector.__enter__()
        attempts = 60
        while attempts > 0:
            self.publish({"tgt_type": "glob", "tgt": "*", "jid": -1, "start": True})
            if self.collector.running.wait(1) is True:
                break
            attempts -= 1
        else:
            pytest.fail("Failed to confirm the collector has started")
        return self

    def __exit__(self, *args):
        # Publish a payload to tell the collection it's done processing
        self.publish({"tgt_type": "glob", "tgt": "*", "jid": -1, "stop": True})
        # Now trigger the collector to also exit
        self.collector.__exit__(*args)
        # We can safely wait here without a timeout because the Collector instance has a
        # hard timeout set, so eventually Collector.stopped will be set
        self.collector.stopped.wait()
        # Stop our own processing
        self.queue.put(None)
        # Wait at most 10 secs for the above `None` in the queue to be processed
        self.stopped.wait(10)
        self.close()
        self.terminate()
        log.info("The PubServerChannelProcess has terminated")


@pytest.fixture(params=["tcp", "zeromq"])
def transport(request):
    yield request.param


@pytest.mark.skip_on_windows
@pytest.mark.slow_test
def test_publish_to_pubserv_ipc(salt_master, salt_minion, transport):
    """
    Test sending 10K messags to ZeroMQPubServerChannel using IPC transport

    ZMQ's ipc transport not supported on Windows
    """
    opts = dict(
        salt_master.config.copy(), ipc_mode="ipc", pub_hwm=0, transport=transport
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
def test_issue_36469_tcp(salt_master, salt_minion):
    """
    Test sending both large and small messags to publisher using TCP

    https://github.com/saltstack/salt/issues/36469
    """

    def _send_small(opts, sid, num=10):
        server_channel = salt.transport.server.PubServerChannel.factory(opts)
        for idx in range(num):
            load = {"tgt_type": "glob", "tgt": "*", "jid": "{}-s{}".format(sid, idx)}
            server_channel.publish(load)
        time.sleep(3)
        server_channel.close_pub()

    def _send_large(opts, sid, num=10, size=250000 * 3):
        server_channel = salt.transport.server.PubServerChannel.factory(opts)
        for idx in range(num):
            load = {
                "tgt_type": "glob",
                "tgt": "*",
                "jid": "{}-l{}".format(sid, idx),
                "xdata": "0" * size,
            }
            server_channel.publish(load)
        time.sleep(3)
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
        expect.extend(["{}-s{}".format(a, b) for a in range(10) for b in (1, 3)])
        expect.extend(["{}-l{}".format(a, b) for a in range(10) for b in (2, 4)])
    results = server_channel.collector.results
    assert len(results) == send_num, "{} != {}, difference: {}".format(
        len(results), send_num, set(expect).difference(results)
    )


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
