# -*- coding: utf-8 -*-
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


# Define a function alias in order not to shadow built-in's
__func_alias__ = {
    'list_': 'list'
}

# Define the module's virtual name
__virtualname__ = 'raid'


def __virtual__():
    '''
    mdadm provides raid functions for Linux
    '''
    if __grains__['kernel'] != 'Linux':
        return False
    if not salt.utils.which('mdadm'):
        return False
    return __virtualname__


def list_():
    '''
    List the RAID devices.

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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
        if ':' not in line:
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


def destroy(device):
    '''
    Destroy a RAID device.

    WARNING This will zero the superblock of all members of the RAID array..

    CLI Example:

    .. code-block:: bash

        salt '*' raid.destroy /dev/md0
    '''
    try:
        details = detail(device)
    except CommandExecutionError:
        return False

    stop_cmd = 'mdadm --stop {0}'.format(device)
    zero_cmd = 'mdadm --zero-superblock {0}'

    if __salt__['cmd.retcode'](stop_cmd):
        for number in details['members']:
            __salt__['cmd.retcode'](zero_cmd.format(number['device']))

    # Remove entry from config file:
    if __grains__.get('os_family') == 'Debian':
        cfg_file = '/etc/mdadm/mdadm.conf'
    else:
        cfg_file = '/etc/mdadm.conf'

    __salt__['file.replace'](cfg_file, 'ARRAY {0} .*'.format(device), '')

    if __salt__['raid.list']().get(device) is None:
        return True
    else:
        return False


def create(name,
           level,
           devices,
           test_mode=False,
           **kwargs):
    '''
    Create a RAID device.

    .. versionchanged:: 2014.7.0

    .. warning::
        Use with CAUTION, as this function can be very destructive if not used
        properly!

    CLI Examples:

    .. code-block:: bash

        salt '*' raid.create /dev/md0 level=1 chunk=256 ['/dev/xvdd', '/dev/xvde'] test_mode=True

    .. note::

        Adding ``test_mode=True`` as an argument will print out the mdadm
        command that would have been run.

    name
        The name of the array to create.

    level
        The RAID level to use when creating the raid.

    devices
        A list of devices used to build the array.

    kwargs
        Optional arguments to be passed to mdadm.

    returns
        test_mode=True:
            Prints out the full command.
        test_mode=False (Default):
            Executes command on remote the host(s) and
            Prints out the mdadm output.

    .. note::

        It takes time to create a RAID array. You can check the progress in
        "resync_status:" field of the results from the following command:

        .. code-block:: bash

            salt '*' raid.detail /dev/md0

    For more info, read the ``mdadm(8)`` manpage
    '''
    opts = ''
    for key in kwargs:
        if not key.startswith('__'):
            if kwargs[key] is True:
                opts += '--{0} '.format(key)
            else:
                opts += '--{0}={1} '.format(key, kwargs[key])

    cmd = "mdadm -C {0} -v {1}-l {2} -n {3} {4}".format(name,
            opts,
            level,
            len(devices),
            ' '.join(devices))

    if test_mode is True:
        return cmd
    elif test_mode is False:
        return __salt__['cmd.run'](cmd)


def save_config():
    '''
    Save RAID configuration to config file.

    Same as:
    mdadm --detail --scan >> /etc/mdadm/mdadm.conf

    Fixes this issue with Ubuntu
    REF: http://askubuntu.com/questions/209702/why-is-my-raid-dev-md1-showing-up-as-dev-md126-is-mdadm-conf-being-ignored

    CLI Example:

    .. code-block:: bash

        salt '*' raid.save_config

    '''
    scan = __salt__['cmd.run']('mdadm --detail --scan').split()
    # Issue with mdadm and ubuntu
    # REF: http://askubuntu.com/questions/209702/why-is-my-raid-dev-md1-showing-up-as-dev-md126-is-mdadm-conf-being-ignored
    if __grains__['os'] == 'Ubuntu':
        buggy_ubuntu_tags = ['name', 'metadata']
        for bad_tag in buggy_ubuntu_tags:
            for i, elem in enumerate(scan):
                if not elem.find(bad_tag):
                    del scan[i]

    scan = ' '.join(scan)
    if __grains__.get('os_family') == 'Debian':
        cfg_file = '/etc/mdadm/mdadm.conf'
    else:
        cfg_file = '/etc/mdadm.conf'

    if not __salt__['file.search'](cfg_file, scan):
        __salt__['file.append'](cfg_file, scan)

    return __salt__['cmd.run']('update-initramfs -u')
