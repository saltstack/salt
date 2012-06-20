'''
Salt module to manage RAID arrays with mdadm
'''

import logging


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
        if ' ' not in line:
            continue
        comps = line.split()
        device = comps[1]
        ret[device] = {"device": device}
        for comp in comps[2:]:
            key = comp.split('=')[0].lower()
            value = comp.split('=')[1]
            ret[device][key] = value
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
        if ' ' not in line:
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
