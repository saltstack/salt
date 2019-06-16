import logging
import socket

import salt.utils.stringutils
from salt.log.handlers.logstash_mod import DatagramLogstashHandler
from tests.support.unit import TestCase


class DatagramLogstashHandlerTest(TestCase):
    def setUp(self):
        self.test_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.test_server.bind(("127.0.0.1", 12345))
        self.test_server.settimeout(2)
        self.logger = logging.getLogger("test_logstash_logger")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(DatagramLogstashHandler("127.0.0.1", 12345))

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
            self.fail("Log message was not received.\n"
                      "Check either pickling failed (and message was not send) or some other error occurred")
