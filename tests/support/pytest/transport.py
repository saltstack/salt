import ctypes
import hashlib
import logging
import multiprocessing
import queue
import socket
import time

import pytest
import tornado.ioloop
import tornado.iostream
import zmq
from pytestshellutils.utils.processes import terminate_process

import salt.channel.server
import salt.crypt
import salt.exceptions
import salt.master
import salt.payload
import salt.utils.msgpack
import salt.utils.process
import salt.utils.stringutils

log = logging.getLogger(__name__)


class RecvError(Exception):
    """
    Raised by the Collector's _recv method when there is a problem
    getting publishes from to the publisher.
    """


class Collector(salt.utils.process.SignalHandlingProcess):
    def __init__(
        self,
        minion_config,
        interface,
        port,
        aes_key,
        timeout=300,
    ):
        super().__init__()
        self.minion_config = minion_config
        self.hexid = hashlib.sha1(
            salt.utils.stringutils.to_bytes(self.minion_config["id"])
        ).hexdigest()
        self.interface = interface
        self.port = port
        self.aes_key = aes_key
        self.timeout = timeout
        self.aes_key = aes_key
        self.hard_timeout = time.time() + timeout + 120
        self.manager = multiprocessing.Manager()
        self.results = self.manager.list()
        self.zmq_filtering = minion_config["zmq_filtering"]
        self.stopped = multiprocessing.Event()
        self.started = multiprocessing.Event()
        self.running = multiprocessing.Event()
        self.stop_running = multiprocessing.Event()
        self.unpacker = salt.utils.msgpack.Unpacker(raw=False)

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

    def _teardown_listener(self):
        if self.transport == "zeromq":
            self.sock.close()
            self.ctx.term()
        else:
            self.sock.close()

    def _setup_listener(self):
        if self.transport == "zeromq":
            self.ctx = zmq.Context()
            self.sock = self.ctx.socket(zmq.SUB)
            self.sock.setsockopt(zmq.LINGER, -1)
            if self.zmq_filtering:
                self.sock.setsockopt(zmq.SUBSCRIBE, b"broadcast")
                if self.minion_config.get("__role") == "syndic":
                    self.sock.setsockopt(zmq.SUBSCRIBE, b"syndic")
                else:
                    self.sock.setsockopt(
                        zmq.SUBSCRIBE, salt.utils.stringutils.to_bytes(self.hexid)
                    )
            else:
                self.sock.setsockopt(zmq.SUBSCRIBE, b"")
            pub_uri = f"tcp://{self.interface}:{self.port}"
            self.sock.connect(pub_uri)
        else:
            end = time.time() + 120
            while True:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    sock.connect((self.interface, self.port))
                except ConnectionRefusedError:
                    if time.time() >= end:
                        raise
                    time.sleep(1)
                else:
                    break
            self.sock = tornado.iostream.IOStream(sock)

    async def _recv(self):
        if self.transport == "zeromq":
            # test_zeromq_filtering requires catching the
            # SaltDeserializationError in order to pass.
            try:
                messages = self.sock.recv_multipart(flags=zmq.NOBLOCK, copy=True)
                messages_len = len(messages)
                if messages_len == 1:
                    serial_payload = salt.payload.loads(messages[0])
                elif messages_len == 2:
                    message_target = salt.utils.stringutils.to_str(messages[0])
                    is_syndic = self.minion_config.get("__role") == "syndic"
                    if (
                        not is_syndic
                        and message_target not in ("broadcast", self.hexid)
                    ) or (is_syndic and message_target not in ("broadcast", "syndic")):
                        log.debug(
                            "Publish received for not this minion: %s", message_target
                        )
                        return
                    serial_payload = salt.payload.loads(messages[1])
                else:
                    raise Exception("Invalid number of messages")
                return serial_payload
            except (zmq.ZMQError, salt.exceptions.SaltDeserializationError):
                raise RecvError("ZMQ Error")
        else:
            for msg in self.unpacker:
                serial_payload = salt.payload.loads(msg["body"])
                return serial_payload
            byts = await self.sock.read_bytes(8096, partial=True)
            self.unpacker.feed(byts)
            for msg in self.unpacker:
                serial_payload = salt.payload.loads(msg["body"])
                return serial_payload
            raise RecvError("TCP Error")

    async def _run(self, loop):
        try:
            self._setup_listener()
        except Exception:  # pylint: disable=broad-except
            self.started.set()
            log.exception("Failed to start listening")
            return
        self.started.set()
        last_msg = time.time()
        self.start = last_msg
        crypticle = salt.crypt.Crypticle(self.minion_config, self.aes_key)
        self.gotone = False
        try:
            while True:
                curr_time = time.time()
                if time.time() > self.hard_timeout:
                    log.error("Hard timeout reached in test collector!")
                    break
                if curr_time - last_msg >= self.timeout:
                    log.error("Receive timeout reached in test collector!")
                    break
                try:
                    payload = await self._recv()
                except RecvError:
                    time.sleep(0.03)
                else:
                    try:
                        log.trace("Colleted payload %r", payload)
                        payload = crypticle.loads(payload["load"])
                        if not payload:
                            continue
                        if "start" in payload:
                            log.info("Collector started")
                            self.running.set()
                            continue
                        if "stop" in payload:
                            log.info("Collector stopped")
                            self.stop_running.set()
                            break
                        last_msg = time.time()
                        self.results.append(payload["jid"])
                    except salt.exceptions.SaltDeserializationError:
                        log.error("Deserializer Error")
                        if not self.zmq_filtering:
                            log.exception("Failed to deserialize...")
                            break
                    if self.gotone is False:
                        log.debug("Collector started recieving")
                    self.gotone = True
            log.debug("Collector finished recieving")
            self.end = time.time()
            print(f"Total time {self.end - self.start}")
        finally:
            self._teardown_listener()
            loop.stop()

    def run(self):
        """
        Gather results until then number of seconds specified by timeout passes
        without receiving a message
        """
        loop = tornado.ioloop.IOLoop()
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
        self.name = "PubServerChannelProcess"
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
        self.pub_server_channel = salt.channel.server.PubServerChannel.factory(
            self.master_config
        )
        self.pub_server_channel.pre_fork(self.process_manager)
        self.pub_uri = "tcp://{interface}:{publish_port}".format(**self.master_config)
        self.queue = multiprocessing.Queue()
        self.stopped = multiprocessing.Event()
        self.collector = Collector(
            self.minion_config,
            self.master_config["interface"],
            self.master_config["publish_port"],
            self.aes_key,
            **self.collector_kwargs,
        )

    def run(self):
        ioloop = tornado.ioloop.IOLoop()
        try:
            while True:
                try:
                    payload = self.queue.get(False)
                except queue.Empty:
                    if self._closing is True:
                        break
                    time.sleep(0.03)
                    continue
                if payload is None:
                    log.debug("We received the stop sentinel")
                    break
                ioloop.run_sync(lambda: self.pub_server_channel.publish(payload))
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
        if hasattr(self.pub_server_channel, "close"):
            self.pub_server_channel.close()
        # Really terminate any process still left behind
        for pid in self.process_manager._process_map:
            terminate_process(pid=pid, kill_children=True, slow_stop=False)
        self.process_manager = None

    def publish(self, payload):
        self.queue.put(payload)

    def __enter__(self):
        self.start()
        self.collector.__enter__()
        attempts = 300
        while attempts > 0:
            self.publish({"tgt_type": "glob", "tgt": "*", "jid": -1, "start": True})
            if self.collector.running.wait(1) is True:
                break
            time.sleep(0.5)
            attempts -= 1
        else:
            pytest.fail("Failed to confirm the collector has started")
        return self

    def __exit__(self, *args):
        # Publish a payload to tell the collection it's done processing
        attempts = 300
        while attempts > 0:
            self.publish({"tgt_type": "glob", "tgt": "*", "jid": -1, "stop": True})
            if self.collector.stop_running.wait(1) is True:
                break
            time.sleep(0.5)
            attempts -= 1
        else:
            pytest.fail("Failed to confirm the collector has stopped")
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
