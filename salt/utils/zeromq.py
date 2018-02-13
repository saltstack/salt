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
        if not tornado.version_info >= (5,):
            ZMQDefaultLoop = zmq.eventloop.ioloop.ZMQIOLoop
    except ImportError:
        ZMQDefaultLoop = None
    if ZMQDefaultLoop is None:
        ZMQDefaultLoop = tornado.ioloop.IOLoop

# Build version info
if zmq:
    if hasattr(zmq, 'zmq_version_info'):
        zmq_version_info = zmq.zmq_version_info()
    else:
        # PyZMQ <= 2.1.9 does not have zmq_version_info, fall back to
        # using zmq.zmq_version() and build a version info tuple.
        zmq_version_info = tuple([int(v_el) for v_el in zmq.zmq_version().split('.')])
else:
    zmq_version_info = (-1, -1, -1)


def install_zmq():
    '''
    While pyzmq 17 no longer needs any special integration for tornado,
    older version still need one.
    :return:
    '''
    if zmq and ZMQ_VERSION_INFO[0] < 17:
        if not tornado.version_info >= (5,):
            zmq.eventloop.ioloop.install()


def check_ipc_path_max_len(uri):
    # The socket path is limited to 107 characters on Solaris and
    # Linux, and 103 characters on BSD-based systems.
    if zmq is None:
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
