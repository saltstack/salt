# -*- coding: utf-8 -*-
'''
:requires: clustershell
https://github.com/cea-hpc/clustershell

This roster resolves hostname in a pdsh/clustershell style.

When you want to use host globs for target matching, use --roster clustershell.

Example:
    salt-ssh --roster clustershell 'server_[1-10,21-30],test_server[5,7,9]' test.ping
'''

# Import python libs
from __future__ import absolute_import
import socket

from salt.ext.six.moves import map  # pylint: disable=import-error,redefined-builtin
from ClusterShell.NodeSet import NodeSet


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
    addrs = [socket.gethostbyname(h) for h in hosts]

    for addr in addrs:
        addr = str(addr)
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(float(__opts__['ssh_scan_timeout']))
                sock.connect((addr, port))
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
                ret[addr] = {'host': addr, 'port': port}
            except socket.error:
                pass
    return ret
