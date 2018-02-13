# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

import logging
import tornado.ioloop
from salt.exceptions import SaltSystemExit

log = logging.getLogger(__name__)

try:
    import zmq
except ImportError:
    zmq = None
    log.debug('ZMQ module is not found')

ZMQDefaultLoop = None
ZMQ_VERSION_INFO = (-1, -1, -1)

try:
    if zmq:
        ZMQ_VERSION_INFO = [int(v_el) for v_el in zmq.__version__.split('.')]
        if ZMQ_VERSION_INFO[0] > 16:  # 17.0.x+ deprecates zmq's ioloops
            ZMQDefaultLoop = tornado.ioloop.IOLoop
except Exception as ex:
    log.exception(ex)

if ZMQDefaultLoop is None:
    try:
        import zmq.eventloop.ioloop
        # Support for ZeroMQ 13.x
        if not hasattr(zmq.eventloop.ioloop, 'ZMQIOLoop'):
            zmq.eventloop.ioloop.ZMQIOLoop = zmq.eventloop.ioloop.IOLoop
        ZMQDefaultLoop = zmq.eventloop.ioloop.ZMQIOLoop
    except ImportError:
        ZMQDefaultLoop = tornado.ioloop.IOLoop




def check_ipc_path_max_len(uri):
    # The socket path is limited to 107 characters on Solaris and
    # Linux, and 103 characters on BSD-based systems.
    if not HAS_ZMQ:
        return
    ipc_path_max_len = getattr(zmq, 'IPC_PATH_MAX_LEN', 103)
    if ipc_path_max_len and len(uri) > ipc_path_max_len:
        raise SaltSystemExit(
            'The socket path is longer than allowed by OS. '
            '\'{0}\' is longer than {1} characters. '
            'Either try to reduce the length of this setting\'s '
            'path or switch to TCP; in the configuration file, '
            'set "ipc_mode: tcp".'.format(
                uri, ipc_path_max_len
            )
        )
