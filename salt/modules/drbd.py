# -*- coding: utf-8 -*-
'''
DRBD administration module
'''

import os.path
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
        fields = line.strip().split()
        minnum=fields[0].split(':')[0]
        device=fields[0].split(':')[1]
        connstate=fields.pop()
        role=fields.pop().split('/')
        localrole=role[0]
        partnerrole=role[1]
        diskstate=fields.pop().split('/')
        localdiskstate=diskstate[0]
        partnerdiskstate=diskstate[1]
        mountpoint=fields.pop()
        fs_mounted=fields.pop()
        totalsize=fields.pop()
        usedsize=fields.pop()
        remainsize=fields.pop()
        perc=fields.pop()
        ret[key] = {
        'minor number':minnum,
        'device':device,
        'connection state':connstate,
        'local role':localrole,
        'partner role':partnerrole,
        'local disk state':localdiskstate,
        'partner disk state':partnerdiskstate,
        'mountpoint':mountpoint,
        'fs':fs_mounted,
        'total size':totalsize,
        'used':usedsize,
        'remains':remainsize,
        'percent':perc,
        }
    return ret