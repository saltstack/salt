# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.payload_test
    ~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import time
import errno
import threading
import datetime

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON

# Import Salt libs
from salt.utils import immutabletypes
from salt.utils.odict import OrderedDict
import salt.exceptions
import salt.payload

# Import 3rd-party libs
import zmq
from salt.ext import six

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
        payload = salt.payload.Serial('msgpack')
        idata = {'pillar': [OrderedDict(environment='dev')]}
        odata = payload.loads(payload.dumps(idata.copy()))
        self.assertNoOrderedDict(odata)
        self.assertEqual(idata, odata)

    def test_datetime_dump_load(self):
        '''
        Check the custom datetime handler can understand itself
        '''
        payload = salt.payload.Serial('msgpack')
        dtvalue = datetime.datetime(2001, 2, 3, 4, 5, 6, 7)
        idata = {dtvalue: dtvalue}
        sdata = payload.dumps(idata.copy())
        odata = payload.loads(sdata)
        self.assertEqual(
                sdata,
                b'\x81\xc7\x18N20010203T04:05:06.000007\xc7\x18N20010203T04:05:06.000007')
        self.assertEqual(idata, odata)

    def test_verylong_dump_load(self):
        '''
        Test verylong encoder/decoder
        '''
        payload = salt.payload.Serial('msgpack')
        idata = {'jid': 20180227140750302662}
        sdata = payload.dumps(idata.copy())
        odata = payload.loads(sdata)
        idata['jid'] = '{0}'.format(idata['jid'])
        self.assertEqual(idata, odata)

    def test_immutable_dict_dump_load(self):
        '''
        Test immutable dict encoder/decoder
        '''
        payload = salt.payload.Serial('msgpack')
        idata = {'dict': {'key': 'value'}}
        sdata = payload.dumps({'dict': immutabletypes.ImmutableDict(idata['dict'])})
        odata = payload.loads(sdata)
        self.assertEqual(idata, odata)

    def test_immutable_list_dump_load(self):
        '''
        Test immutable list encoder/decoder
        '''
        payload = salt.payload.Serial('msgpack')
        idata = {'list': [1, 2, 3]}
        sdata = payload.dumps({'list': immutabletypes.ImmutableList(idata['list'])})
        odata = payload.loads(sdata)
        self.assertEqual(idata, odata)

    def test_immutable_set_dump_load(self):
        '''
        Test immutable set encoder/decoder
        '''
        payload = salt.payload.Serial('msgpack')
        idata = {'set': ['red', 'green', 'blue']}
        sdata = payload.dumps({'set': immutabletypes.ImmutableSet(idata['set'])})
        odata = payload.loads(sdata)
        self.assertEqual(idata, odata)

    def test_odict_dump_load(self):
        '''
        Test odict just works. It wasn't until msgpack 0.2.0
        '''
        payload = salt.payload.Serial('msgpack')
        data = OrderedDict()
        data['a'] = 'b'
        data['y'] = 'z'
        data['j'] = 'k'
        data['w'] = 'x'
        sdata = payload.dumps({'set': data})
        odata = payload.loads(sdata)
        self.assertEqual({'set': dict(data)}, odata)

    def test_mixed_dump_load(self):
        '''
        Test we can handle all exceptions at once
        '''
        payload = salt.payload.Serial('msgpack')
        dtvalue = datetime.datetime(2001, 2, 3, 4, 5, 6, 7)
        od = OrderedDict()
        od['a'] = 'b'
        od['y'] = 'z'
        od['j'] = 'k'
        od['w'] = 'x'
        idata = {dtvalue: dtvalue,  # datetime
                 'jid': 20180227140750302662,  # long int
                 'dict': immutabletypes.ImmutableDict({'key': 'value'}),  # immutable dict
                 'list': immutabletypes.ImmutableList([1, 2, 3]),  # immutable list
                 'set': immutabletypes.ImmutableSet(('red', 'green', 'blue')),  # immutable set
                 'odict': od,  # odict
                 }
        edata = {dtvalue: dtvalue,  # datetime, == input
                 'jid': '20180227140750302662',  # string repr of long int
                 'dict': {'key': 'value'},  # builtin dict
                 'list': [1, 2, 3],  # builtin list
                 'set': ['red', 'green', 'blue'],  # builtin set
                 'odict': dict(od),  # builtin dict
                 }
        sdata = payload.dumps(idata)
        odata = payload.loads(sdata)
        self.assertEqual(edata, odata)


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
                    log.info('Echo server received message: %s', msg_deserialized)
                    if isinstance(msg_deserialized['load'], dict) and msg_deserialized['load'].get('sleep'):
                        log.info('Test echo server sleeping for %s seconds',
                                 msg_deserialized['load']['sleep'])
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
