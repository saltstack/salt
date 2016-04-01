# -*- coding: utf-8 -*-
'''
Support for haproxy

.. versionadded:: 2014.7.0
'''

from __future__ import generators
from __future__ import absolute_import

# Import python libs
import stat
import os
import logging

try:
    import haproxy.cmds
    import haproxy.conn
    HAS_HAPROXY = True
except ImportError:
    HAS_HAPROXY = False

log = logging.getLogger(__name__)

__virtualname__ = 'haproxy'


def __virtual__():
    '''
    Only load the module if haproxyctl is installed
    '''
    if HAS_HAPROXY:
        return __virtualname__
    return False


def _get_conn(socket='/var/run/haproxy.sock'):
    '''
    Get connection to haproxy socket.
    '''
    assert os.path.exists(socket), '{0} does not exist.'.format(socket)
    issock = os.stat(socket).st_mode
    assert stat.S_ISSOCK(issock), '{0} is not a socket.'.format(socket)
    ha_conn = haproxy.conn.HaPConn(socket)
    return ha_conn


def list_servers(backend, socket='/var/run/haproxy.sock', objectify=False):
    '''
    List servers in haproxy backend.

    backend
        haproxy backend

    socket
        haproxy stats socket

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.list_servers mysql
    '''
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.listServers(backend=backend)
    return ha_conn.sendCmd(ha_cmd, objectify=objectify)


def enable_server(name, backend, socket='/var/run/haproxy.sock'):
    '''
    Enable Server in haproxy

    name
        Server to enable

    backend
        haproxy backend

    socket
        haproxy stats socket

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.enable_server web1.example.com www
    '''
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.enableServer(server=name, backend=backend)
    ha_conn.sendCmd(ha_cmd)
    return list_servers(backend, socket=socket)


def disable_server(name, backend, socket='/var/run/haproxy.sock'):
    '''
    Disable server in haproxy.

    name
        Server to disable

    backend
        haproxy backend

    socket
        haproxy stats socket

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.disable_server db1.example.com mysql
    '''
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.disableServer(server=name, backend=backend)
    ha_conn.sendCmd(ha_cmd)
    return list_servers(backend, socket=socket)


def get_weight(name, backend, socket='/var/run/haproxy.sock'):
    '''
    Get server weight

    name
        Server name

    backend
        haproxy backend

    socket
        haproxy stats socket

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.get_weight web1.example.com www
    '''
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.getWeight(server=name, backend=backend)
    return ha_conn.sendCmd(ha_cmd)


def set_weight(name, backend, weight=0, socket='/var/run/haproxy.sock'):
    '''
    Set server weight

    name
        Server name

    backend
        haproxy backend

    weight
        Server Weight

    socket
        haproxy stats socket

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.set_weight web1.example.com www 13
    '''
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.getWeight(server=name, backend=backend, weight=weight)
    ha_conn.sendCmd(ha_cmd)
    return get_weight(name, backend, socket=socket)


def show_frontends(socket='/var/run/haproxy.sock'):
    '''
    Show HaProxy frontends

    socket
        haproxy stats socket

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.show_frontends
    '''
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.showFrontends()
    return ha_conn.sendCmd(ha_cmd)


def show_backends(socket='/var/run/haproxy.sock'):
    '''
    Show HaProxy Backends

    socket
        haproxy stats socket

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.show_backends
    '''
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.showBackends()
    return ha_conn.sendCmd(ha_cmd)
