# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.payload_test
    ~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Salt libs
from __future__ import absolute_import
import time
import errno
import threading

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.helpers import MockWraps
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch

# Import salt libs
import salt.payload
from salt.utils.odict import OrderedDict
import salt.exceptions

# Import 3rd-party libs
import msgpack
import zmq
import salt.ext.six as six

import logging

log = logging.getLogger(__name__)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PayloadTestCase(TestCase):

    def assertNoOrderedDict(self, data):
        if isinstance(data, OrderedDict):
            raise AssertionError(
                'Found an ordered dictionary'
            )
        if isinstance(data, dict):
            for value in six.itervalues(data):
                self.assertNoOrderedDict(value)
        elif isinstance(data, (list, tuple)):
            for chunk in data:
                self.assertNoOrderedDict(chunk)

    def test_list_nested_odicts(self):
        with patch('msgpack.version', (0, 1, 13)):
            msgpack.dumps = MockWraps(
                msgpack.dumps, 1, TypeError('ODict TypeError Forced')
            )
            payload = salt.payload.Serial('msgpack')
            idata = {'pillar': [OrderedDict(environment='dev')]}
            odata = payload.loads(payload.dumps(idata.copy()))
            self.assertNoOrderedDict(odata)
            self.assertEqual(idata, odata)


class SREQTestCase(TestCase):
    port = 8845  # TODO: dynamically assign a port?

    @classmethod
    def setUpClass(cls):
        '''
        Class to set up zmq echo socket
        '''
        def echo_server():
            '''
            A server that echos the message sent to it over zmq

            Optional "sleep" can be sent to delay response
            '''
            context = zmq.Context()
            socket = context.socket(zmq.REP)
            socket.bind("tcp://*:{0}".format(SREQTestCase.port))
            payload = salt.payload.Serial('msgpack')

            while SREQTestCase.thread_running.is_set():
                try:
                    #  Wait for next request from client
                    message = socket.recv(zmq.NOBLOCK)
                    msg_deserialized = payload.loads(message)
                    log.info('Echo server received message: {0}'.format(msg_deserialized))
                    if isinstance(msg_deserialized['load'], dict) and msg_deserialized['load'].get('sleep'):
                        log.info('Test echo server sleeping for {0} seconds'.format(msg_deserialized['load']['sleep']))
                        time.sleep(msg_deserialized['load']['sleep'])
                    socket.send(message)
                except zmq.ZMQError as exc:
                    if exc.errno == errno.EAGAIN:
                        continue
                    raise
        SREQTestCase.thread_running = threading.Event()
        SREQTestCase.thread_running.set()
        SREQTestCase.echo_server = threading.Thread(target=echo_server)
        SREQTestCase.echo_server.start()

    @classmethod
    def tearDownClass(cls):
        '''
        Remove echo server
        '''
        # kill the thread
        SREQTestCase.thread_running.clear()
        SREQTestCase.echo_server.join()

    def get_sreq(self):
        return salt.payload.SREQ('tcp://127.0.0.1:{0}'.format(SREQTestCase.port))

    def test_send_auto(self):
        '''
        Test creation, send/rect
        '''
        sreq = self.get_sreq()
        # check default of empty load and enc clear
        assert sreq.send_auto({}) == {'enc': 'clear', 'load': {}}

        # check that the load always gets passed
        assert sreq.send_auto({'load': 'foo'}) == {'load': 'foo', 'enc': 'clear'}

    def test_send(self):
        sreq = self.get_sreq()
        assert sreq.send('clear', 'foo') == {'enc': 'clear', 'load': 'foo'}

    @skipIf(True, 'Disabled until we can figure out how to make this more reliable.')
    def test_timeout(self):
        '''
        Test SREQ Timeouts
        '''
        sreq = self.get_sreq()
        # client-side timeout
        start = time.time()
        # This is a try/except instead of an assertRaises because of a possible
        # subtle bug in zmq wherein a timeout=0 actually exceutes a single poll
        # before the timeout is reached.
        log.info('Sending tries=0, timeout=0')
        try:
            sreq.send('clear', 'foo', tries=0, timeout=0)
        except salt.exceptions.SaltReqTimeoutError:
            pass
        assert time.time() - start < 1  # ensure we didn't wait

        # server-side timeout
        log.info('Sending tries=1, timeout=1')
        start = time.time()
        with self.assertRaises(salt.exceptions.SaltReqTimeoutError):
            sreq.send('clear', {'sleep': 2}, tries=1, timeout=1)
        assert time.time() - start >= 1  # ensure we actually tried once (1s)

        # server-side timeout with retries
        log.info('Sending tries=2, timeout=1')
        start = time.time()
        with self.assertRaises(salt.exceptions.SaltReqTimeoutError):
            sreq.send('clear', {'sleep': 2}, tries=2, timeout=1)
        assert time.time() - start >= 2  # ensure we actually tried twice (2s)

        # test a regular send afterwards (to make sure sockets aren't in a twist
        log.info('Sending regular send')
        assert sreq.send('clear', 'foo') == {'enc': 'clear', 'load': 'foo'}

    def test_destroy(self):
        '''
        Test the __del__ capabilities
        '''
        sreq = self.get_sreq()
        # ensure no exceptions when we go to destroy the sreq, since __del__
        # swallows exceptions, we have to call destroy directly
        sreq.destroy()
