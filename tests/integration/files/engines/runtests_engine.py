# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2015 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    pytestsalt.engines.pytest_engine
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Simple salt engine which will setup a socket to accept connections allowing us to know
    when a daemon is up and running
'''

# Import python libs
from __future__ import absolute_import
import socket
import logging

# Import salt libs
import salt.utils.event

# Import 3rd-party libs
from tornado import gen
from tornado import ioloop
from tornado import netutil

log = logging.getLogger(__name__)

__virtualname__ = 'salt_runtests'


def __virtual__():
    return 'runtests_conn_check_port' in __opts__  # pylint: disable=undefined-variable


def start():
    # Create our own IOLoop, we're in another process
    io_loop = ioloop.IOLoop()
    io_loop.make_current()
    pytest_engine = PyTestEngine(__opts__, io_loop)  # pylint: disable=undefined-variable
    io_loop.add_callback(pytest_engine.start)
    io_loop.start()


class PyTestEngine(object):
    def __init__(self, opts, io_loop):
        self.opts = opts
        self.io_loop = io_loop
        self.sock = None

    @gen.coroutine
    def start(self):
        if self.opts['__role'] == 'minion':
            yield self.listen_to_minion_connected_event()

        port = int(self.opts['runtests_conn_check_port'])
        log.info('Starting Pytest Engine(role=%s) on port %s', self.opts['__role'], port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(0)
        # bind the socket to localhost on the config provided port
        self.sock.bind(('localhost', port))
        # become a server socket
        self.sock.listen(5)
        netutil.add_accept_handler(
            self.sock,
            self.handle_connection,
            io_loop=self.io_loop,
        )

    def handle_connection(self, connection, address):
        log.warning('Accepted connection from %s. Role: %s', address, self.opts['__role'])
        # We just need to know that the daemon running the engine is alive...
        connection.shutdown(socket.SHUT_RDWR)  # pylint: disable=no-member
        connection.close()

    @gen.coroutine
    def listen_to_minion_connected_event(self):
        log.info('Listening for minion connected event...')
        minion_start_event_match = 'salt/minion/{0}/start'.format(self.opts['id'])
        event_bus = salt.utils.event.get_master_event(self.opts,
                                                      self.opts['sock_dir'],
                                                      listen=True)
        event_bus.subscribe(minion_start_event_match)
        while True:
            event = event_bus.get_event(full=True, no_block=True)
            if event is not None and event['tag'] == minion_start_event_match:
                log.info('Got minion connected event: %s', event)
                break
            yield gen.sleep(0.25)
