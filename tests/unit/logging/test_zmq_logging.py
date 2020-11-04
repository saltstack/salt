import logging
import multiprocessing
import threading
import time

import salt.utils.msgpack
import zmq
from saltfactories.utils.ports import get_unused_localhost_port
from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


def logging_target(running_event, host, port):
    # It should be running already, but let's wait nonetheless
    running_event.wait(10)
    try:
        # Remove any other log handlers inherited
        logging._acquireLock()  # pylint: disable=protected-access
        logging.root.handlers[:] = []
        handler = salt._logging.handlers.ZMQHandler(host=host, port=port)
        handler.setLevel(logging.DEBUG)
        logging.root.addHandler(handler)
    finally:
        logging._releaseLock()

    _log = logging.getLogger("test_zmq_logging")
    _log.setLevel(logging.DEBUG)
    _log.debug("Go! Handlers: %s", logging.root.handlers)

    def foo():
        # This will raise an exception
        foo = object().foo

    def bar():
        # Wrap the exception in multiple methods too make the stack bigger
        foo()

    try:
        foo()
    except AttributeError:
        _log.exception("TEST-ü")
    finally:
        # See the comment on ZMQHandler.start on why we have to call stop
        # explicitly because this code is running in a multiprocessing.Process
        handler.stop()


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
        log.warning("Sending the stop sentinel to the thread processing the ZMQ logs")
        context = zmq.Context()
        sender = context.socket(zmq.PUSH)
        sender.connect("tcp://{}:{}".format(self.host, self.port))
        try:
            sender.send(salt.utils.msgpack.dumps(None))
            iteration = 0
            while self.running_event.is_set():
                iteration += 1
                if iteration >= 10:
                    log.warning("The stop sentinel wasn't received yet")
                time.sleep(0.5)
        finally:
            sender.close(1)
            context.term()

    def tearDown(self):
        self.send_consumer_shutdown()
        self.log_consumer.join()

    def test_zmq_logging(self):
        with TstSuiteLoggingHandler(level=logging.ERROR) as handler:
            proc = multiprocessing.Process(
                target=logging_target, args=(self.running_event, self.host, self.port),
            )
            proc.start()
            proc.join(5)
            if proc.exitcode is None:
                log.warning(
                    "The process being tested did not exit after 5 seconds. Killing it."
                )
                # 5 seconds was more than enough for the process to exit cleanly. Kill it.
                proc.terminate()
            assert len(handler.messages) == 1, len(handler.messages)
            record = handler.messages[0]
            assert "TEST-ü" in record
            assert "Traceback" in record
