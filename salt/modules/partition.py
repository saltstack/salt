'''
Module for managing partitions on posix-like systems
'''

import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on posix-like systems
    '''
    # Disable on these platorms, specific service modules exist:
    disable = [
        'Windows',
        ]
    if __grains__['os'] in disable:
        return False
    return 'partition'


def probe(device=''):
    '''
    Ask the kernel to update its local partition data

    CLI Examples::

        salt '*' partition.probe
        salt '*' partition.probe /dev/sda
    '''
    cmd = 'partprobe {0}'.format(device)
    out = __salt__['cmd.run'](cmd).splitlines()
    return out


def partlist(device, unit=None):
    '''
    Ask the kernel to update its local partition data

    CLI Examples::

        salt '*' partition.partlist /dev/sda
        salt '*' partition.partlist /dev/sda unit=s
        salt '*' partition.partlist /dev/sda unit=kB
    '''
    if unit:
        cmd = 'parted -s {0} unit {1} print'.format(device, unit)
    else:
        cmd = 'parted -s {0} print'.format(device)
    out = __salt__['cmd.run'](cmd).splitlines()
    ret = {'info': [], 'partitions': {}}
    mode = 'info'
    for line in out:
        if not line:
            continue
        if mode == 'info':
            if line.startswith('Number'):
                mode = 'partitions'
            else:
                ret['info'].append(line)
        else:
            comps = line.strip().split()
            ret['partitions'][comps[0]] = {
                'number': comps[0],
                'start': comps[1],
                'end': comps[2],
                'size': comps[3],
                'type': comps[4]}
            if len(comps) > 5:
                ret['partitions'][comps[0]]['file system'] = comps[5]
            if len(comps) > 6:
                ret['partitions'][comps[0]]['flags'] = comps[6:]
    return ret

