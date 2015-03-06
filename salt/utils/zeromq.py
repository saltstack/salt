# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
from salt.exceptions import SaltSystemExit

# Import 3rd-party libs
try:
    import zmq
    HAS_ZMQ = True
except ImportError:
    HAS_ZMQ = False


def check_ipc_path_max_len(uri):
    # The socket path is limited to 107 characters on Solaris and
    # Linux, and 103 characters on BSD-based systems.
    if not HAS_ZMQ:
        return
    ipc_path_max_len = getattr(zmq, 'IPC_PATH_MAX_LEN', 103)
    if ipc_path_max_len and len(uri) > ipc_path_max_len:
        raise SaltSystemExit(
            'The socket path is longer than allowed by OS. '
            '{0!r} is longer than {1} characters. '
            'Either try to reduce the length of this setting\'s '
            'path or switch to TCP; in the configuration file, '
            'set "ipc_mode: tcp".'.format(
                uri, ipc_path_max_len
            )
        )
