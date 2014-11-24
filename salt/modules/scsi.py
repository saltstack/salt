# -*- coding: utf-8 -*-
'''
SCSI administration module
'''
from __future__ import absolute_import

import os.path
import logging

log = logging.getLogger(__name__)

__func_alias__ = {
    'ls_': 'ls'
}


def ls_():
    '''
    List SCSI devices, with details

    CLI Example:

    .. code-block:: bash

        salt '*' scsi.ls
    '''
    cmd = 'lsscsi -dLsv'
    ret = {}
    for line in __salt__['cmd.run'](cmd).splitlines():
        if line.startswith('['):
            mode = 'start'
            comps = line.strip().split()
            key = comps[0]
            size = comps.pop()
            majmin = comps.pop()
            major, minor = majmin.replace('[', '').replace(']', '').split(':')
            device = comps.pop()
            model = ' '.join(comps[3:])
            ret[key] = {
                'lun': key.replace('[', '').replace(']', ''),
                'size': size,
                'major': major,
                'minor': minor,
                'device': device,
                'model': model,
            }
        elif line.startswith(' '):
            if line.strip().startswith('dir'):
                comps = line.strip().split()
                ret[key]['dir'] = [
                    comps[1],
                    comps[2].replace('[', '').replace(']', '')
                ]
            else:
                comps = line.strip().split('=')
                ret[key][comps[0]] = comps[1]
    return ret


def rescan_all(host):
    '''
    List scsi devices

    CLI Example:

    .. code-block:: bash

        salt '*' scsi.rescan_all(0)
    '''
    if os.path.isdir('/sys/class/scsi_host/host{0}'.format(host)):
        cmd = 'echo "- - -" > /sys/class/scsi_host/host{0}/scan'.format(host)
    else:
        return 'Host {0} does not exist'.format(host)
    return __salt__['cmd.run'](cmd).splitlines()
