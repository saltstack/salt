# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import multiprocessing
import threading
import time

import zmq
import msgpack

import salt.log.setup
import salt.log.handlers

from tests.integration import get_unused_localhost_port
from tests.support.unit import TestCase


class TestLogHandler(logging.NullHandler):

    def __init__(self, level=logging.NOTSET):
        super(TestLogHandler, self).__init__(level=level)
        self.messages = []

    def handle(self, record):
        self.messages.append(record)


def logging_target(host, port):
    log = logging.getLogger('test_zmq_logging')
    log.handlers = []
    handler = salt.log.handlers.ZMQHandler(host=host, port=port)
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
        time.sleep(1)


class TestZMQLogging(TestCase):

    def setUp(self):
        opts = {
            'log_level': 'INFO',
            'log_fmt_console': '%(message)s',
            'log_datefmt_console': '%H:%M:%S',
            'log_datefmt_logfile': '%Y-%m-%d %H:%M:%S',
            'log_file': 'test.log',
        }
        self.port = get_unused_localhost_port()
        self.host = '127.0.0.1'
        self.logger = logging.getLogger('test_zmq_logging')
        self.handler = TestLogHandler(level='DEBUG')
        self.logger.addHandler(self.handler)
        # Run the consumer in a thread so we can access the handler's messages
        # attribute later.
        self.log_consumer = threading.Thread(
            target=salt.log.setup._process_multiprocessing_logging_zmq,
            args=(opts, self.port, True)
        )
        self.log_consumer.start()
        # Allow time for the consumer to get all connected
        time.sleep(5)

    def send_consumer_shutdown(self):
        context = zmq.Context()
        sender = context.socket(zmq.PUSH)
        sender.connect('tcp://{}:{}'.format(self.host, self.port))
        try:
            sender.send(msgpack.dumps(None))
        finally:
            sender.close(1)
            context.term()

    def tearDown(self):
        self.send_consumer_shutdown()
        self.log_consumer.join()

    def test_zmq_logging(self):
        proc = multiprocessing.Process(
            target=logging_target,
            args=(self.host, self.port),
        )
        proc.start()
        proc.join()
        assert len(self.handler.messages) == 1, len(self.handler.messages)
        record = self.handler.messages[0]
        assert 'TEST-ü' in record.msg
        assert 'Traceback' in record.msg
