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
    return (False, 'The haproxyconn execution module cannot be loaded: haproxyctl module not available')


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
        haproxy backend, or all backends if "*" is supplied

    socket
        haproxy stats socket

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.enable_server web1.example.com www
    '''

    if backend == '*':
        backends = show_backends(socket=socket).split('\n')
    else:
        backends = [backend]

    results = {}
    for backend in backends:
        ha_conn = _get_conn(socket)
        ha_cmd = haproxy.cmds.enableServer(server=name, backend=backend)
        ha_conn.sendCmd(ha_cmd)
        results[backend] = list_servers(backend, socket=socket)

    return results


def disable_server(name, backend, socket='/var/run/haproxy.sock'):
    '''
    Disable server in haproxy.

    name
        Server to disable

    backend
        haproxy backend, or all backends if "*" is supplied

    socket
        haproxy stats socket

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.disable_server db1.example.com mysql
    '''

    if backend == '*':
        backends = show_backends(socket=socket).split('\n')
    else:
        backends = [backend]

    results = {}
    for backend in backends:
        ha_conn = _get_conn(socket)
        ha_cmd = haproxy.cmds.disableServer(server=name, backend=backend)
        ha_conn.sendCmd(ha_cmd)
        results[backend] = list_servers(backend, socket=socket)

    return results


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


def set_state(name, backend, state, socket='/var/run/haproxy.sock'):
    '''
    Force a server's administrative state to a new state. This can be useful to
    disable load balancing and/or any traffic to a server. Setting the state to
    "ready" puts the server in normal mode, and the command is the equivalent of
    the "enable server" command. Setting the state to "maint" disables any traffic
    to the server as well as any health checks. This is the equivalent of the
    "disable server" command. Setting the mode to "drain" only removes the server
    from load balancing but still allows it to be checked and to accept new
    persistent connections. Changes are propagated to tracking servers if any.

    name
        Server name

    backend
        haproxy backend

    state
        A string of the state to set. Must be 'ready', 'drain', or 'maint'

    '''
    # Pulling this in from the latest 0.5 release which is not yet in PyPi.
    # https://github.com/neurogeek/haproxyctl
    class setServerState(haproxy.cmds.Cmd):
        """Set server state command."""
        cmdTxt = "set server %(backend)s/%(server)s state %(value)s\r\n"
        p_args = ['backend', 'server', 'value']
        helpTxt = "Force a server's administrative state to a new state."

    ha_conn = _get_conn(socket)
    ha_cmd = setServerState(server=name, backend=backend, value=state)
    return ha_conn.sendCmd(ha_cmd)


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


def get_sessions(name, backend, socket='/var/run/haproxy.sock'):
    '''
    .. versionadded:: Carbon

    Get number of current sessions on server in backend (scur)

    name
        Server name

    backend
        haproxy backend

    socket
        haproxy stats socket

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.get_sessions web1.example.com www
    '''
    class getStats(haproxy.cmds.Cmd):
        p_args = ["backend", "server"]
        cmdTxt = "show stat\r\n"
        helpText = "Fetch all statistics"

    ha_conn = _get_conn(socket)
    ha_cmd = getStats(server=name, backend=backend)
    result = ha_conn.sendCmd(ha_cmd)
    for line in result.split('\n'):
        if line.startswith(backend):
            outCols = line.split(',')
            if outCols[1] == name:
                return outCols[4]
