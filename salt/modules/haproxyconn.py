# -*- coding: utf-8 -*-
'''
Support for haproxy
'''

from __future__ import generators

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


# Import salt libs
import salt.utils

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
    assert os.path.exists(socket), '{0} does not exist.'.format(socket)
    issock = os.stat(socket).st_mode
    assert stat.S_ISSOCK(issock), '{0} is not a socket.'.format(socket)
    ha_conn = haproxy.conn.HaPConn(socket)
    return ha_conn


def list_servers(backend, socket='/var/run/haproxy.sock'):
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.listServers(backend=backend)
    ha_conn.sendCmd(ha_cmd)


def enable_server(name, backend, socket='/var/run/haproxy.sock'):
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.enableServer(server=name, backend=backend)
    ha_conn.sendCmd(ha_cmd)
    return list_servers(backend)


def disable_server(name, backend, socket='/var/run/haproxy.sock'):
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.disableServer(server=name, backend=backend)
    ha_conn.sendCmd(ha_cmd)
    return list_servers(backend)


def get_weight(name, backend, socket='/var/run/haproxy.sock'):
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.getWeight(server=name, backend=backend)
    ha_conn.sendCmd(ha_cmd)
    return list_servers(backend)


def set_weight(name, backend, weight=0, socket='/var/run/haproxy.sock'):
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.getWeight(server=name, backend=backend, weight=weight)
    ha_conn.sendCmd(ha_cmd)
    return list_servers(backend)


def show_frontends(socket='/var/run/haproxy.sock'):
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.showFrontends()
    return ha_conn.sendCmd(ha_cmd)


def show_backends(socket='/var/run/haproxy.sock'):
    ha_conn = _get_conn(socket)
    ha_cmd = haproxy.cmds.showBackends()
    return ha_conn.sendCmd(ha_cmd)
