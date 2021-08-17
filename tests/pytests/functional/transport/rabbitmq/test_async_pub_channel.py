import ctypes
import logging
import multiprocessing
import signal
import time

import pytest
import salt.config
import salt.exceptions
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.log.setup
import salt.transport.client
import salt.transport.server
import salt.transport.rabbitmq
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
from saltfactories.utils.processes import terminate_process

from salt.ext import tornado

log = logging.getLogger(__name__)


class Collector(salt.utils.process.SignalHandlingProcess):
    """
    A process for collecting published events
    """
    def __init__(
        self, minion_config, pub_uri, aes_key, timeout=30
    ):
        super().__init__()
        self.minion_config = minion_config
        self.pub_uri = pub_uri
        self.aes_key = aes_key
        self.timeout = timeout
        self.hard_timeout = time.time() + timeout + 30
        self.manager = multiprocessing.Manager()
        self.results = self.manager.list()
        self.stopped = multiprocessing.Event()
        self.started = multiprocessing.Event()
        self.running = multiprocessing.Event()
        self.last_message_timestamp = time.time()

    def run(self):
        # receive
        io_loop = tornado.ioloop.IOLoop.instance()

        """
        Gather results until then number of seconds specified by timeout passes
        without receiving a message
        """
        serial = salt.payload.Serial(self.minion_config)
        crypticle = salt.crypt.Crypticle(self.minion_config, self.aes_key)
        self.started.set()

        def callback(payload):
            curr_time = time.time()
            if time.time() > self.hard_timeout:
                io_loop.stop()
                return
            if curr_time - self.last_message_timestamp >= self.timeout:
                io_loop.stop()
                return
            try:
                serial_payload = serial.loads(payload)
                serial_payload = serial.loads(serial_payload['payload'])
                payload = crypticle.loads(serial_payload["load"])
                if "start" in payload:
                    self.running.set()
                    return
                if "stop" in payload:
                    io_loop.stop()
                    return
                self.last_message_timestamp = time.time()
                self.results.append(payload["jid"])
            except salt.exceptions.SaltDeserializationError:
                log.exception("Failed to deserialize...")

        rmq_connection_wrapper = salt.transport.rabbitmq.RMQNonBlockingConnectionWrapper(
            self.minion_config,
            io_loop=io_loop,
            timeout=self.hard_timeout)
        rmq_connection_wrapper.register_message_callback(callback)

        io_loop.start()

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
    """
    Publisher
    """
    def __init__(self, master_config, minion_config, **collector_kwargs):
        super().__init__()
        self._closing = False
        self.master_config = master_config
        self.minion_config = minion_config
        self.collector_kwargs = collector_kwargs
        self.aes_key = multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        )
        self.process_manager = None

        self.pub_uri = "tcp://{interface}:{publish_port}".format(**self.master_config)
        self.queue = multiprocessing.Queue()
        self.stopped = multiprocessing.Event()
        self.collector = Collector(
            self.minion_config,
            self.pub_uri,
            self.aes_key.value,
            **self.collector_kwargs
        )

    def run(self):
        salt.master.SMaster.secrets["aes"] = {"secret": self.aes_key}
        pub_server_channel = salt.transport.rabbitmq.RabbitMQPubServerChannel(
            self.master_config
        )
        pub_server_channel.pre_fork(
            self.process_manager,
            kwargs={"log_queue": salt.log.setup.get_multiprocessing_logging_queue()},
        )

        try:
            while True:
                payload = self.queue.get()
                if payload is None:
                    log.debug("We received the stop signal")
                    break
                pub_server_channel.publish(payload)
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
        self.process_manager.stop_restarting()
        self.process_manager.send_signal_to_processes(signal.SIGTERM)
        self.process_manager.kill_children()
        # Really terminate any process still left behind
        for pid in self.process_manager._process_map:
            terminate_process(pid=pid, kill_children=True, slow_stop=False)
        self.process_manager = None

    def publish(self, payload):
        self.queue.put(payload)

    def __enter__(self):
        self.start()
        self.collector.__enter__()
        attempts = 30
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


@pytest.mark.slow_test
def test_publish_to_pubserv_ipc_async_collector(salt_master, salt_minion):
    """
    Test sending a message to RabbitMQPubServerChannel using IPC transport
    To start rmq container: "docker run  --name rabbitmq -p 5672:5672 -p 15672:15672 bitnami/rabbitmq"
    """
    opts = dict(salt_master.config.copy(), ipc_mode="ipc", pub_hwm=0)
    # this starts the receiver that blocks
    with PubServerChannelProcess(opts, salt_minion.config.copy()) as server_channel:
        send_num = 4
        expect = []
        for idx in range(send_num):
            expect.append(idx)
            load = {"tgt_type": "glob", "tgt": "*", "jid": idx}
            server_channel.publish(load) # publish N messages
    results = server_channel.collector.results
    assert len(results) == send_num, "{} != {}, difference: {}".format(
        len(results), send_num, set(expect).difference(results)
    )

