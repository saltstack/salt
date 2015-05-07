# -*- coding: utf-8 -*-
'''
Scan a netmask or ipaddr for open ssh ports
'''

# Import python libs
from __future__ import absolute_import
import socket

# Import salt libs
import salt.utils.network
import salt.ext.ipaddress as ipaddress
from salt.ext.six.moves import map  # pylint: disable=import-error,redefined-builtin


def targets(tgt, tgt_type='glob', **kwargs):
    '''
    Return the targets from the flat yaml file, checks opts for location but
    defaults to /etc/salt/roster
    '''
    rmatcher = RosterMatcher(tgt, tgt_type)
    return rmatcher.targets()


class RosterMatcher(object):
    '''
    Matcher for the roster data structure
    '''
    def __init__(self, tgt, tgt_type):
        self.tgt = tgt
        self.tgt_type = tgt_type

    def targets(self):
        '''
        Return ip addrs based on netmask, sitting in the "glob" spot because
        it is the default
        '''
        addrs = ()
        ret = {}
        ports = __opts__['ssh_scan_ports']
        if not isinstance(ports, list):
            # Comma-separate list of integers
            ports = list(map(int, str(ports).split(',')))
        try:
            addrs = [ipaddress.ip_address(self.tgt)]
        except ValueError:
            try:
                addrs = ipaddress.ip_network(self.tgt).hosts()
            except ValueError:
                pass
        for addr in addrs:
            for port in ports:
                try:
                    sock = salt.utils.network.get_socket(addr, socket.SOCK_STREAM)
                    sock.settimeout(float(__opts__['ssh_scan_timeout']))
                    sock.connect((str(addr), port))
                    sock.shutdown(socket.SHUT_RDWR)
                    sock.close()
                    ret[addr] = {'host': addr, 'port': port}
                except socket.error:
                    pass
        return ret
