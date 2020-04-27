# -*- coding: utf-8 -*-
from __future__ import absolute_import

import errno
import logging
import socket
import time

import salt.utils.stringutils
import zmq
from salt.log.handlers.logstash_mod import DatagramLogstashHandler, ZMQLogstashHander
from tests.support.helpers import get_unused_localhost_port
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


# At the moment of writing this test the `functional` suite is not yet complete
# TODO move to the `functional` suite since this test doesn't require running instance of Salt Master/Minion
class DatagramLogstashHandlerTest(TestCase):
    def setUp(self):
        self.test_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        port = get_unused_localhost_port()
        self.test_server.bind(("127.0.0.1", port))
        self.test_server.settimeout(2)
        self.logger = logging.getLogger("test_logstash_logger")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(DatagramLogstashHandler("127.0.0.1", port))

    def tearDown(self):
        self.test_server.close()

    def test_log_pickling(self):
        # given
        the_log = "test message"

        # when
        self.logger.info(the_log)

        # then
        try:
            received_log, addr = self.test_server.recvfrom(12)
            self.assertEqual(received_log, salt.utils.stringutils.to_bytes(the_log))
        except socket.timeout:
            self.fail(
                "Log message was not received.\n"
                "Check either pickling failed (and message was not send) or some other error occurred"
            )


# At the moment of writing this test the `functional` suite is not yet complete
# TODO move to the `functional` suite since this test doesn't require running instance of Salt Master/Minion
class ZMQLogstashHanderTest(TestCase):
    def setUp(self):
        self.context = zmq.Context()
        port = get_unused_localhost_port()

        self.zmq_server = self.context.socket(zmq.SUB)
        self.zmq_server.setsockopt(zmq.SUBSCRIBE, b"")
        self.zmq_server.bind("tcp://127.0.0.1:{}".format(port))

        self.logger = logging.getLogger("test_logstash_logger")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(ZMQLogstashHander("tcp://127.0.0.1:{}".format(port)))

    def tearDown(self):
        self.zmq_server.close()
        self.context.term()

    def test_log_pickling(self):
        # given
        the_log = "test message"
        attempts = 5
        received_log = "wrong message"

        # I couldn't receive the first log message, that's why it is done using loop...
        # https://zeromq.jira.com/browse/LIBZMQ-270 could be related
        while attempts >= 0:
            try:
                # when
                self.logger.info(the_log)
                time.sleep(1)
                received_log = self.zmq_server.recv(zmq.NOBLOCK)

                # then
                break
            except zmq.ZMQError as exc:
                if exc.errno == errno.EAGAIN:
                    attempts -= 1
                    continue
                raise

        self.assertEqual(
            received_log,
            salt.utils.stringutils.to_bytes(the_log),
            "Check either pickling failed (and message was not send) or some other error occurred",
        )
