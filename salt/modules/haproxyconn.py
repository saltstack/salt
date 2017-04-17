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
import time

try:
    import haproxy.cmds
    import haproxy.conn
    HAS_HAPROXY = True
except ImportError:
    HAS_HAPROXY = False

log = logging.getLogger(__name__)

__virtualname__ = 'haproxy'

# Default socket location
DEFAULT_SOCKET_URL = '/var/run/haproxy.sock'

# Numeric fields returned by stats
FIELD_NUMERIC = ["weight", "bin", "bout"]
# Field specifying the actual server name
FIELD_NODE_NAME = "name"


def __virtual__():
    '''
    Only load the module if haproxyctl is installed
    '''
    if HAS_HAPROXY:
        return __virtualname__
    return (False, 'The haproxyconn execution module cannot be loaded: haproxyctl module not available')


def _get_conn(socket=DEFAULT_SOCKET_URL):
    '''
    Get connection to haproxy socket.
    '''
    assert os.path.exists(socket), '{0} does not exist.'.format(socket)
    issock = os.stat(socket).st_mode
    assert stat.S_ISSOCK(issock), '{0} is not a socket.'.format(socket)
    ha_conn = haproxy.conn.HaPConn(socket)
    return ha_conn


def list_servers(backend, socket=DEFAULT_SOCKET_URL, objectify=False):
    '''
    List servers in haproxy backend.

    backend
        haproxy backend

    socket
        haproxy stats socket, default ``/var/run/haproxy.sock``

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.list_servers mysql
    '''
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.listServers(backend=backend)
    return ha_conn.sendCmd(ha_cmd, objectify=objectify)


def wait_state(backend, server, value='up', timeout=60*5, socket=DEFAULT_SOCKET_URL):
    '''

    Wait for a specific server state

    backend
        haproxy backend

    server
        targeted server

    value
        state value

    timeout
        timeout before giving up state value, default 5 min

    socket
        haproxy stats socket, default ``/var/run/haproxy.sock``

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.wait_state mysql server01 up 60
    '''
    t = time.time() + timeout
    while time.time() < t:
        if get_backend(backend=backend, socket=socket)[server]["status"].lower() == value.lower():
            return True
    return False


def get_backend(backend, socket=DEFAULT_SOCKET_URL):
    '''

    Receive information about a specific backend.

    backend
        haproxy backend

    socket
        haproxy stats socket, default ``/var/run/haproxy.sock``

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.get_backend mysql
    '''

    backend_data = list_servers(backend=backend, socket=socket).replace('\n', ' ').split(' ')
    result = {}

    # Convert given string to Integer
    def num(s):
        try:
            return int(s)
        except ValueError:
            return s

    for data in backend_data:
        # Check if field or server name
        if ":" in data:
            active_field = data.replace(':', '').lower()
            continue
        elif active_field.lower() == FIELD_NODE_NAME:
            active_server = data
            result[active_server] = {}
            continue
        # Format and set returned field data to active server
        if active_field in FIELD_NUMERIC:
            if data == "":
                result[active_server][active_field] = 0
            else:
                result[active_server][active_field] = num(data)
        else:
            result[active_server][active_field] = data

    return result


def enable_server(name, backend, socket=DEFAULT_SOCKET_URL):
    '''
    Enable Server in haproxy

    name
        Server to enable

    backend
        haproxy backend, or all backends if "*" is supplied

    socket
        haproxy stats socket, default ``/var/run/haproxy.sock``

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


def disable_server(name, backend, socket=DEFAULT_SOCKET_URL):
    '''
    Disable server in haproxy.

    name
        Server to disable

    backend
        haproxy backend, or all backends if "*" is supplied

    socket
        haproxy stats socket, default ``/var/run/haproxy.sock``

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


def get_weight(name, backend, socket=DEFAULT_SOCKET_URL):
    '''
    Get server weight

    name
        Server name

    backend
        haproxy backend

    socket
        haproxy stats socket, default ``/var/run/haproxy.sock``

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.get_weight web1.example.com www
    '''
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.getWeight(server=name, backend=backend)
    return ha_conn.sendCmd(ha_cmd)


def set_weight(name, backend, weight=0, socket=DEFAULT_SOCKET_URL):
    '''
    Set server weight

    name
        Server name

    backend
        haproxy backend

    weight
        Server Weight

    socket
        haproxy stats socket, default ``/var/run/haproxy.sock``

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.set_weight web1.example.com www 13
    '''
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.getWeight(server=name, backend=backend, weight=weight)
    ha_conn.sendCmd(ha_cmd)
    return get_weight(name, backend, socket=socket)


def set_state(name, backend, state, socket=DEFAULT_SOCKET_URL):
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

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.set_state my_proxy_server my_backend ready

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


def show_frontends(socket=DEFAULT_SOCKET_URL):
    '''
    Show HaProxy frontends

    socket
        haproxy stats socket, default ``/var/run/haproxy.sock``

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.show_frontends
    '''
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.showFrontends()
    return ha_conn.sendCmd(ha_cmd)


def list_frontends(socket=DEFAULT_SOCKET_URL):
    '''

    List HaProxy frontends

    socket
        haproxy stats socket, default ``/var/run/haproxy.sock``

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.list_frontends
    '''
    return show_frontends(socket=socket).split('\n')


def show_backends(socket=DEFAULT_SOCKET_URL):
    '''
    Show HaProxy Backends

    socket
        haproxy stats socket, default ``/var/run/haproxy.sock``

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.show_backends
    '''
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.showBackends()
    return ha_conn.sendCmd(ha_cmd)


def list_backends(servers=True, socket=DEFAULT_SOCKET_URL):
    '''

    List HaProxy Backends

    socket
        haproxy stats socket, default ``/var/run/haproxy.sock``

    servers
        list backends with servers

    CLI Example:

    .. code-block:: bash

        salt '*' haproxy.list_backends
    '''
    if not servers:
        return show_backends(socket=socket).split('\n')
    else:
        result = {}
        for backend in list_backends(servers=False, socket=socket):
            result[backend] = get_backend(backend=backend, socket=socket)
        return result


def get_sessions(name, backend, socket=DEFAULT_SOCKET_URL):
    '''
    .. versionadded:: 2016.11.0

    Get number of current sessions on server in backend (scur)

    name
        Server name

    backend
        haproxy backend

    socket
        haproxy stats socket, default ``/var/run/haproxy.sock``

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
