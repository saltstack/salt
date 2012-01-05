'''
Salt module to manage RAID arrays with mdadm
'''

import logging
import os


# Set up logger
log = logging.getLogger(__name__)


def __virtual__():
    '''
    mdadm provides raid functions for Linux
    '''
    return 'raid' if __grains__['kernel'] == 'Linux' else False


def list():
    '''
    List the RAID devices.

    CLI Example::

        salt '*' raid.list
    '''
    ret = {}
    for line in (__salt__['cmd.run_stdout']
                 ('mdadm --detail --scan').split('\n')):
        if not line.count(' '):
            continue
        comps = line.split()
        metadata = comps[2].split('=')
        raidname = comps[3].split('=')
        raiduuid = comps[4].split('=')
        ret[comps[1]] = {
            'device': comps[1],
            'metadata': metadata[1],
            'name': raidname[1],
            'uuid': raiduuid[1],
        }
    return ret


def detail(device='/dev/md0'):
    '''
    Show detail for a specified RAID device

    CLI Example::

        salt '*' raid.detail '/dev/md0'
    '''
    ret = {}
    ret['members'] = {}
    cmd = 'mdadm --detail %s' % device
    for line in __salt__['cmd.run_stdout'](cmd).split('\n'):
        if line.startswith(device):
            continue
        if not line.count(' '):
            continue
        if not ':' in line:
            if '/dev/' in line:
                comps = line.split()
                state = comps[4:-1]
                ret['members'][comps[0]] = {
                    'device': comps[-1],
                    'major': comps[1],
                    'minor': comps[2],
                    'number': comps[0],
                    'raiddevice': comps[3],
                    'state': ' '.join(state),
                }
            continue
        comps = line.split(' : ')
        comps[0] = comps[0].lower()
        comps[0] = comps[0].strip()
        comps[0] = comps[0].replace(' ', '_')
        ret[comps[0]] = comps[1].strip()
    return ret
