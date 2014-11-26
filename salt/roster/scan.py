# -*- coding: utf-8 -*-
'''
Scan a netmask or ipaddr for open ssh ports
'''
from __future__ import absolute_import

# Import python libs
import socket

# Import salt libs
import salt.ext.ipaddr


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
            salt.ext.ipaddr.IPAddress(self.tgt)
            addrs = [self.tgt]
        except ValueError:
            try:
                addrs = salt.ext.ipaddr.IPNetwork(self.tgt).iterhosts()
            except ValueError:
                pass
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
