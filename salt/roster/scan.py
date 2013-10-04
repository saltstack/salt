# -*- coding: utf-8 -*-
'''
Scan a netmask or ipaddr for open ssh ports
'''

# Import python libs
import socket

# Import salt libs
import salt.utils.ipaddr


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
        try:
            salt.utils.ipaddr.IPAddress(self.tgt)
            addrs = [self.tgt]
        except ValueError:
            try:
                addrs = salt.utils.ipaddr.IPNetwork(self.tgt).iterhosts()
            except ValueError:
                pass
        for addr in addrs:
            addr = str(addr)
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.01)
                sock.connect((addr, 22))
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
                ret[addr] = {'host': addr}
            except socket.error:
                pass
        return ret
