import logging
import multiprocessing
import sys
import threading

import salt.utils.msgpack
import zmq
from saltfactories.utils.ports import get_unused_localhost_port
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.unit import TestCase


def logging_target(running_event, host, port):
    running_event.wait(10)
    log = logging.getLogger(__name__)
    log.handlers[:] = []
    handler = salt._logging.handlers.ZMQHandler(host=host, port=port)
    log.addHandler(handler)

    def foo():
        # This will raise an exception
        foo = object().foo

    def bar():
        # Wrap the exception in multiple methods too make the stack bigger
        foo()

    try:
        foo()
    except AttributeError:
        log.exception("TEST-ü")
    finally:
        log.removeHandler(handler)
        # Calling stop will flush any remaining unsent messages
        handler.stop()
        sys.exit(0)


class TestZMQLogging(TestCase):
    def setUp(self):
        self.port = get_unused_localhost_port()
        self.host = "127.0.0.1"
        self.running_event = multiprocessing.Event()
        # Run the consumer in a thread so we can access the handler's messages
        # attribute later.
        self.log_consumer = threading.Thread(
            target=salt._logging.impl._log_forwarding_consumer,
            args=(self.running_event, self.host, self.port),
            kwargs={"setup_signal_handling": False},
        )
        for attrname in ("port", "host", "running_event", "log_consumer"):
            self.addCleanup(delattr, self, attrname)
        self.log_consumer.start()
        # Allow time for the consumer to get all connected
        self.running_event.wait(15)

    def send_consumer_shutdown(self):
        context = zmq.Context()
        sender = context.socket(zmq.PUSH)
        sender.connect("tcp://{}:{}".format(self.host, self.port))
        try:
            sender.send(salt.utils.msgpack.dumps(None))
        finally:
            sender.close(1500)
            context.term()

    def tearDown(self):
        self.send_consumer_shutdown()
        self.running_event.clear()
        # Wait 5 seconds for the process to terminate
        self.log_consumer.join(5)
        if self.log_consumer.exitcode is None:
            # The process did not finish by itself.
            self.log_consumer.kill()

    def test_zmq_logging(self):
        with TstSuiteLoggingHandler(level=logging.ERROR) as handler:
            proc = multiprocessing.Process(
                target=logging_target, args=(self.running_event, self.host, self.port),
            )
            proc.start()
            proc.join()
            assert len(handler.messages) == 1, len(handler.messages)
            record = handler.messages[0]
            assert "TEST-ü" in record
            assert "Traceback" in record
