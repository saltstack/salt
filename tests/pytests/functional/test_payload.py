import errno
import logging
import threading
import time

import pytest
import zmq

import salt.exceptions
import salt.payload

log = logging.getLogger(__name__)


@pytest.fixture
def echo_port():
    yield 8845


class EchoServer:
    def __init__(self, port=8845):
        self.thread_running = threading.Event()
        self.thread_running.set()
        self.port = port
        self.thread = threading.Thread(
            target=self.echo_server, args=(port, self.thread_running)
        )

    def start(self):
        self.thread.start()
        time.sleep(1)

    def stop(self):
        self.thread_running.clear()
        self.thread.join()

    @staticmethod
    def echo_server(port, event):
        """
        A server that echos the message sent to it over zmq

        Optional "sleep" can be sent to delay response
        """
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind(f"tcp://*:{port}")
        while event.is_set():
            try:
                #  Wait for next request from client
                message = socket.recv(zmq.NOBLOCK)
                msg_deserialized = salt.payload.loads(message)
                log.info("Echo server received message: %s", msg_deserialized)
                if isinstance(msg_deserialized["load"], dict) and msg_deserialized[
                    "load"
                ].get("sleep"):
                    log.info(
                        "Test echo server sleeping for %s seconds",
                        msg_deserialized["load"]["sleep"],
                    )
                    time.sleep(msg_deserialized["load"]["sleep"])
                socket.send(message)  # pylint: disable=missing-kwoa
            except zmq.ZMQError as exc:
                if exc.errno == errno.EAGAIN:
                    continue
                raise


@pytest.fixture
def echo_server(echo_port):
    server = EchoServer()
    server.start()
    try:
        yield server
    finally:
        server.stop()


@pytest.fixture
def sreq(echo_port):
    yield salt.payload.SREQ(f"tcp://127.0.0.1:{echo_port}")


@pytest.mark.slow_test
def test_send_auto(sreq, echo_server):
    """
    Test creation, send/rect
    """
    # check default of empty load and enc clear
    assert sreq.send_auto({}) == {"enc": "clear", "load": {}}

    # check that the load always gets passed
    assert sreq.send_auto({"load": "foo"}) == {"load": "foo", "enc": "clear"}


@pytest.mark.slow_test
def test_send(sreq, echo_server):
    assert sreq.send("clear", "foo") == {"enc": "clear", "load": "foo"}


@pytest.mark.skip("Disabled until we can figure out how to make this more reliable.")
def test_timeout(sreq, echo_server):
    """
    Test SREQ Timeouts
    """
    # client-side timeout
    start = time.time()
    # This is a try/except instead of an assertRaises because of a possible
    # subtle bug in zmq wherein a timeout=0 actually executes a single poll
    # before the timeout is reached.
    log.info("Sending tries=0, timeout=0")
    try:
        sreq.send("clear", "foo", tries=0, timeout=0)
    except salt.exceptions.SaltReqTimeoutError:
        pass
    assert time.time() - start < 1  # ensure we didn't wait

    # server-side timeout
    log.info("Sending tries=1, timeout=1")
    start = time.time()
    with pytest.raises(salt.exceptions.SaltReqTimeoutError):
        sreq.send("clear", {"sleep": 2}, tries=1, timeout=1)
    assert time.time() - start >= 1  # ensure we actually tried once (1s)

    # server-side timeout with retries
    log.info("Sending tries=2, timeout=1")
    start = time.time()
    with pytest.raises(salt.exceptions.SaltReqTimeoutError):
        sreq.send("clear", {"sleep": 2}, tries=2, timeout=1)
    assert time.time() - start >= 2  # ensure we actually tried twice (2s)

    # test a regular send afterwards (to make sure sockets aren't in a twist
    log.info("Sending regular send")
    assert sreq.send("clear", "foo") == {"enc": "clear", "load": "foo"}


@pytest.mark.slow_test
def test_destroy(sreq, echo_server):
    """
    Test the __del__ capabilities
    """
    # ensure we actually have an open socket and not just testing against
    # no actual sockets created.
    assert sreq.send("clear", "foo") == {"enc": "clear", "load": "foo"}
    # ensure no exceptions when we go to destroy the sreq, since __del__
    # swallows exceptions, we have to call destroy directly
    sreq.destroy()


@pytest.mark.slow_test
def test_clear_socket(sreq, echo_server):
    # ensure we actually have an open socket and not just testing against
    # no actual sockets created.
    assert sreq.send("clear", "foo") == {"enc": "clear", "load": "foo"}
    assert hasattr(sreq, "_socket")
    sreq.clear_socket()
    assert hasattr(sreq, "_socket") is False
