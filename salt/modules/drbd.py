# -*- coding: utf-8 -*-
'''
DRBD administration module
'''
from __future__ import absolute_import, print_function, unicode_literals

import logging

log = logging.getLogger(__name__)


def overview():
    '''
    Show status of the DRBD devices

    CLI Example:

    .. code-block:: bash

        salt '*' drbd.overview
    '''
    cmd = 'drbd-overview'
    for line in __salt__['cmd.run'](cmd).splitlines():
        ret = {}
        fields = line.strip().split()
        minnum = fields[0].split(':')[0]
        device = fields[0].split(':')[1]
        connstate = fields[1]
        role = fields[2].split('/')
        localrole = role[0]
        partnerrole = role[1]
        diskstate = fields[3].split('/')
        localdiskstate = diskstate[0]
        partnerdiskstate = diskstate[1]
        if localdiskstate == "UpToDate":
            if partnerdiskstate == "UpToDate":
                if fields[4]:
                    mountpoint = fields[4]
                    fs_mounted = fields[5]
                    totalsize = fields[6]
                    usedsize = fields[7]
                    remainsize = fields[8]
                    perc = fields[9]
                    ret = {
                        'minor number': minnum,
                        'device': device,
                        'connection state': connstate,
                        'local role': localrole,
                        'partner role': partnerrole,
                        'local disk state': localdiskstate,
                        'partner disk state': partnerdiskstate,
                        'mountpoint': mountpoint,
                        'fs': fs_mounted,
                        'total size': totalsize,
                        'used': usedsize,
                        'remains': remainsize,
                        'percent': perc,
                    }
                else:
                    ret = {
                        'minor number': minnum,
                        'device': device,
                        'connection state': connstate,
                        'local role': localrole,
                        'partner role': partnerrole,
                        'local disk state': localdiskstate,
                        'partner disk state': partnerdiskstate,
                    }
            else:
                syncbar = fields[4]
                synced = fields[6]
                syncedbytes = fields[7]
                sync = synced+syncedbytes
                ret = {
                    'minor number': minnum,
                    'device': device,
                    'connection state': connstate,
                    'local role': localrole,
                    'partner role': partnerrole,
                    'local disk state': localdiskstate,
                    'partner disk state': partnerdiskstate,
                    'synchronisation: ': syncbar,
                    'synched': sync,
                }
    return ret
