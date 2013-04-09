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


def destroy(device):
    '''
    Destroy a RAID device.

    WARNING This will zero the superblock of all members of the RAID array..

    CLI Example::

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

    if __salt__['raid.list']().get(device) is None:
        return True
    else:
        return False


def create(*args):
    '''
    Create a RAID device.

    WARNING!! Use with CAUTION, as this function can be very destructive if not
    used properly!

    Use it just as a regular mdadm command.

    For more info, read 'man mdadm'

    NOTE: It takes time to create a RAID array. You can check the progress in
    "resync_status:" field of command:

        salt '*' raid.detail /dev/md0

    CLI Examples::

        Test mode: if you add a test_mode=True as an argument - it will print out the command to double check.

            salt '*' raid.create /dev/md0 level=1 chunk=256 raid-devices=2 /dev/xvdd /dev/xvde test_mode=True

        NON-Testing mode:

            salt '*' raid.create /dev/md0 level=1 chunk=256 raid-devices=2 /dev/xvdd /dev/xvde

    :param args: The arguments u pass to this function.
    :param arguments:
        arguments['new_array']: The name of the new RAID array that will be created.
        arguments['opt_val']: Option with Value. Example: raid-devices=2
        arguments['opt_raw']: Option without Value. Example: force
        arguments['disks_to_array']: The disks that will be added to the new raid.
    :return:
        test_mode=True:
            Prints out the full command.
        test_mode=False (Default):
            Executes command on remote the host(s) and
            Prints out the mdadm output.
    '''
    test_mode = False
    arguments = {'new_array': '', 'opt_val': {}, 'opt_raw': [], "disks_to_array": []}

    for arg in args:
        if arg.startswith('test_mode'):
            test_mode = bool(arg.split('=')[-1])
        elif arg.startswith('/dev/') is True:
            if arg.startswith('/dev/md') is True:
                arguments['new_array'] = arg
            else:
                arguments['disks_to_array'].append(arg)
        elif arg.find('=') != -1:
            opt, val = arg.split('=')
            arguments['opt_val'][opt] = val
        elif str(arg) in ['readonly', 'run', 'force']:
            arguments['opt_raw'].append(arg)
        elif str(arg) in ['missing']:
            arguments['disks_to_array'].append(arg)
        else:
            msg = "Invalid argument - {0} !"
            raise CommandExecutionError(msg.format(arg))

    cmd = "echo y | mdadm --create --verbose {new_array}{opts_raw}{opts_val} {disks_to_array}"
    cmd = cmd.format(new_array=arguments['new_array'],
                     opts_raw=(' --' + ' --'.join(arguments['opt_raw'])
                               if len(arguments['opt_raw']) > 0
                               else ''),
                     opts_val=(' --' + ' --'.join(key + '=' + arguments['opt_val'][key] for key in arguments['opt_val'])
                               if len(arguments['opt_val']) > 0
                               else ''),
                     disks_to_array=' '.join(arguments['disks_to_array']))

    if test_mode is True:
        return cmd
    elif test_mode is False:
        return __salt__['cmd.run'](cmd)
