# -*- coding: utf-8 -*-
'''
ZMQ-specific functions
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import tornado.ioloop
from salt.exceptions import SaltSystemExit
from salt._compat import ipaddress

log = logging.getLogger(__name__)

try:
    import zmq
except ImportError:
    zmq = None
    log.debug('ZMQ module is not found')

ZMQDefaultLoop = None
ZMQ_VERSION_INFO = (-1, -1, -1)
LIBZMQ_VERSION_INFO = (-1, -1, -1)

try:
    if zmq:
        ZMQ_VERSION_INFO = tuple([int(v_el) for v_el in zmq.__version__.split('.')])
        LIBZMQ_VERSION_INFO = tuple([int(v_el) for v_el in zmq.zmq_version().split('.')])
        if ZMQ_VERSION_INFO[0] > 16:  # 17.0.x+ deprecates zmq's ioloops
            ZMQDefaultLoop = tornado.ioloop.IOLoop
except Exception:
    log.exception('Error while getting LibZMQ/PyZMQ library version')

if ZMQDefaultLoop is None:
    try:
        import zmq.eventloop.ioloop
        # Support for ZeroMQ 13.x
        if not hasattr(zmq.eventloop.ioloop, 'ZMQIOLoop'):
            zmq.eventloop.ioloop.ZMQIOLoop = zmq.eventloop.ioloop.IOLoop
        if tornado.version_info < (5,):
            ZMQDefaultLoop = zmq.eventloop.ioloop.ZMQIOLoop
    except ImportError:
        ZMQDefaultLoop = None
    if ZMQDefaultLoop is None:
        ZMQDefaultLoop = tornado.ioloop.IOLoop


def install_zmq():
    '''
    While pyzmq 17 no longer needs any special integration for tornado,
    older version still need one.
    :return:
    '''
    # The zmq module is mocked in Sphinx, so when we build the docs
    # ZMQ_VERSION_INFO ends up being an empty tuple. Using a tuple comparison
    # instead of checking the first element of ZMQ_VERSION_INFO will prevent an
    # IndexError when this function is invoked during the docs build.
    if zmq and ZMQ_VERSION_INFO < (17,):
        if tornado.version_info < (5,):
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


def ip_bracket(addr):
    '''
    Ensure IP addresses are URI-compatible - specifically, add brackets
    around IPv6 literals if they are not already present.
    '''
    addr = str(addr)
    addr = addr.lstrip('[')
    addr = addr.rstrip(']')
    addr = ipaddress.ip_address(addr)
    return ('[{}]' if addr.version == 6 else '{}').format(addr)
