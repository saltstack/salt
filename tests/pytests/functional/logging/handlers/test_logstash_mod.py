import errno
import logging
import socket
import time

import pytest
import salt.utils.stringutils
import zmq
from salt.log.handlers.logstash_mod import DatagramLogstashHandler, ZMQLogstashHander
from saltfactories.utils.ports import get_unused_localhost_port

log = logging.getLogger(__name__)


@pytest.fixture
def datagram_server():
    logger = logging.getLogger("test_logstash_logger")
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    port = get_unused_localhost_port()
    handler = DatagramLogstashHandler("127.0.0.1", port)
    try:
        server.bind(("127.0.0.1", port))
        server.settimeout(2)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        yield server
    finally:
        logger.removeHandler(handler)
        server.close()


@pytest.fixture
def zmq_server():
    logger = logging.getLogger("test_logstash_logger")
    context = zmq.Context()
    server = context.socket(zmq.SUB)
    port = get_unused_localhost_port()
    handler = ZMQLogstashHander("tcp://127.0.0.1:{}".format(port))
    try:
        server.setsockopt(zmq.SUBSCRIBE, b"")
        server.bind("tcp://127.0.0.1:{}".format(port))

        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        yield server
    finally:
        logger.removeHandler(handler)
        server.close()
        context.term()


@pytest.mark.slow_test
def test_datagram_handler_log_pickling(datagram_server):
    # given
    the_log = "test message"

    # when
    logger = logging.getLogger("test_logstash_logger")
    logger.info(the_log)

    # then
    received_log, _ = datagram_server.recvfrom(12)
    assert received_log == salt.utils.stringutils.to_bytes(the_log)


def test_zmq_handler_log_pickling(zmq_server):
    # given
    the_log = "test message"
    attempts = 5
    received_log = "wrong message"
    logger = logging.getLogger("test_logstash_logger")

    # I couldn't receive the first log message, that's why it is done using loop...
    # https://zeromq.jira.com/browse/LIBZMQ-270 could be related
    while attempts >= 0:
        try:
            # when
            logger.info(the_log)
            time.sleep(0.15)
            received_log = zmq_server.recv(zmq.NOBLOCK)
            # then
            break
        except zmq.ZMQError as exc:
            if exc.errno == errno.EAGAIN:
                attempts -= 1
                time.sleep(0.15)
                continue
            raise

    assert received_log == salt.utils.stringutils.to_bytes(the_log)
