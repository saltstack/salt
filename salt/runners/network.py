# -*- coding: utf-8 -*-
'''
Network tools to run from the Master
'''

# Import python libs
from __future__ import print_function
from __future__ import absolute_import
import logging
import socket

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


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
    dest = salt.utils.mac_str_to_bytes(mac)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(b'\xff' * 6 + dest * 16, (bcast, int(destport)))
    return True


def wolmatch(tgt, tgt_type='glob', bcast='255.255.255.255', destport=9):
    '''
    Send a "Magic Packet" to wake up Minions that are matched in the grains cache

    CLI Example:

    .. code-block:: bash

        salt-run network.wolmatch minion_id
        salt-run network.wolmatch 192.168.0.0/16 tgt_type='ipcidr' bcast=255.255.255.255 destport=7
    '''
    ret = []
    minions = __salt__['cache.grains'](tgt, tgt_type)
    for minion in minions:
        for iface, mac in minion['hwaddr_interfaces'].items():
            if iface == 'lo':
                continue
            wol(mac, bcast, destport)
            log.info('Waking up {0}'.format(mac.strip()))
            ret.append(mac)
    return ret
