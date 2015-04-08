# -*- coding: utf-8 -*-
'''
Network tools to run from the Master
'''

# Import python libs
from __future__ import print_function
from __future__ import absolute_import
import socket

# Import salt libs
import salt.utils


def wollist(maclist, bcast='255.255.255.255', destport=9):
    '''
    Send a "Magic Packet" to wake up a list of Minions.
    This list must contain one MAC hardware address per line

    CLI Example:

    .. code-block:: bash

        salt-run network.wollist '/path/to/maclist'
        salt-run network.wollist '/path/to/maclist' 255.255.255.255 7
        salt-run network.wollist '/path/to/maclist' 255.255.255.255 7
    '''
    ret = []
    try:
        with salt.utils.fopen(maclist, 'r') as ifile:
            for mac in ifile:
                wol(mac.strip(), bcast, destport)
                print('Waking up {0}'.format(mac.strip()))
                ret.append(mac)
    except Exception as err:
        __jid_event__.fire_event({'error': 'Failed to open the MAC file. Error: {0}'.format(err)}, 'progress')
        return []
    return ret


def wol(mac, bcast='255.255.255.255', destport=9):
    '''
    Send a "Magic Packet" to wake up a Minion

    CLI Example:

    .. code-block:: bash

        salt-run network.wol 08-00-27-13-69-77
        salt-run network.wol 080027136977 255.255.255.255 7
        salt-run network.wol 08:00:27:13:69:77 255.255.255.255 7
    '''
    if len(mac) == 12:
        pass
    elif len(mac) == 17:
        sep = mac[2]
        mac = mac.replace(sep, '')
    else:
        raise ValueError('Invalid MAC address')
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    dest = ('\\x' + mac[0:2]).decode('string_escape') + \
           ('\\x' + mac[2:4]).decode('string_escape') + \
           ('\\x' + mac[4:6]).decode('string_escape') + \
           ('\\x' + mac[6:8]).decode('string_escape') + \
           ('\\x' + mac[8:10]).decode('string_escape') + \
           ('\\x' + mac[10:12]).decode('string_escape')
    sock.sendto('\xff' * 6 + dest * 16, (bcast, int(destport)))
    return True
