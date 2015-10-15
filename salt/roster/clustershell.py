# -*- coding: utf-8 -*-
'''
This roster resolves hostname in a pdsh/clustershell style.

:depends: clustershell, https://github.com/cea-hpc/clustershell

When you want to use host globs for target matching, use ``--roster clustershell``. For example:

.. code-block:: bash

    salt-ssh --roster clustershell 'server_[1-10,21-30],test_server[5,7,9]' test.ping

'''

# Import python libs
from __future__ import absolute_import
import socket
from salt.ext.six.moves import map  # pylint: disable=import-error,redefined-builtin

REQ_ERROR = None
try:
    from ClusterShell.NodeSet import NodeSet
except (ImportError, OSError) as e:
    REQ_ERROR = 'ClusterShell import error, perhaps missing python ClusterShell package'


def __virtual__():
    return (REQ_ERROR is None, REQ_ERROR)


def targets(tgt, tgt_type='glob', **kwargs):
    '''
    Return the targets
    '''
    ret = {}
    ports = __opts__['ssh_scan_ports']
    if not isinstance(ports, list):
        # Comma-separate list of integers
        ports = list(map(int, str(ports).split(',')))

    hosts = list(NodeSet(tgt))
    host_addrs = dict([(h, socket.gethostbyname(h)) for h in hosts])

    for host, addr in host_addrs.items():
        addr = str(addr)
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(float(__opts__['ssh_scan_timeout']))
                sock.connect((addr, port))
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
                ret[host] = {'host': host, 'port': port}
            except socket.error:
                pass
    return ret
