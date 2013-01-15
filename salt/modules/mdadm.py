'''
Salt module to manage RAID arrays with mdadm
'''

# Import python libs
import os
import logging

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

# Set up logger
log = logging.getLogger(__name__)


def __virtual__():
    '''
    mdadm provides raid functions for Linux
    '''
    if not __grains__['kernel'] == 'Linux':
        return False
    if not salt.utils.which('mdadm'):
        return False
    return 'raid'


def list():
    '''
    List the RAID devices.

    CLI Example::

        salt '*' raid.list
    '''
    ret = {}
    for line in (__salt__['cmd.run_stdout']
                 ('mdadm --detail --scan').splitlines()):
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

    # Lets make sure the device exists before running mdadm
    if not os.path.exists(device):
        msg = "Device {0} doesn't exist!"
        raise CommandExecutionError(msg.format(device))

    cmd = 'mdadm --detail {0}'.format(device)
    for line in __salt__['cmd.run_stdout'](cmd).splitlines():
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
