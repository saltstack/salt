# -*- coding: utf-8 -*-
'''
Module for managing disks and blockdevices
'''
from __future__ import absolute_import

# Import python libs
import logging
import os
import subprocess
import re
import collections
import decimal

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import zip

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.utils.decorators import depends
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

HAS_HDPARM = salt.utils.which('hdparm') is not None
HAS_SMARTCTL = salt.utils.which('smartctl') is not None
HAS_IOSTAT = salt.utils.which('iostat') is not None


def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if salt.utils.is_windows():
        return (False, 'This module doesn\'t work on Windows.')
    return True


def _clean_flags(args, caller):
    '''
    Sanitize flags passed into df
    '''
    flags = ''
    if args is None:
        return flags
    allowed = ('a', 'B', 'h', 'H', 'i', 'k', 'l', 'P', 't', 'T', 'x', 'v')
    for flag in args:
        if flag in allowed:
            flags += flag
        else:
            raise CommandExecutionError(
                'Invalid flag passed to {0}'.format(caller)
            )
    return flags


def usage(args=None):
    '''
    Return usage information for volumes mounted on this minion

    CLI Example:

    .. code-block:: bash

        salt '*' disk.usage
    '''
    flags = _clean_flags(args, 'disk.usage')
    if not os.path.isfile('/etc/mtab') and __grains__['kernel'] == 'Linux':
        log.error('df cannot run without /etc/mtab')
        if __grains__.get('virtual_subtype') == 'LXC':
            log.error('df command failed and LXC detected. If you are running '
                     'a Docker container, consider linking /proc/mounts to '
                     '/etc/mtab or consider running Docker with -privileged')
        return {}
    if __grains__['kernel'] == 'Linux':
        cmd = 'df -P'
    elif __grains__['kernel'] == 'OpenBSD':
        cmd = 'df -kP'
    elif __grains__['kernel'] == 'AIX':
        cmd = 'df -kP'
    else:
        cmd = 'df'
    if flags:
        cmd += ' -{0}'.format(flags)
    ret = {}
    out = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    oldline = None
    for line in out:
        if not line:
            continue
        if line.startswith('Filesystem'):
            continue
        if oldline:
            line = oldline + " " + line
        comps = line.split()
        if len(comps) == 1:
            oldline = line
            continue
        else:
            oldline = None
        while len(comps) >= 2 and not comps[1].isdigit():
            comps[0] = '{0} {1}'.format(comps[0], comps[1])
            comps.pop(1)
        if len(comps) < 2:
            continue
        try:
            if __grains__['kernel'] == 'Darwin':
                ret[comps[8]] = {
                        'filesystem': comps[0],
                        '512-blocks': comps[1],
                        'used': comps[2],
                        'available': comps[3],
                        'capacity': comps[4],
                        'iused': comps[5],
                        'ifree': comps[6],
                        '%iused': comps[7],
                }
            else:
                ret[comps[5]] = {
                        'filesystem': comps[0],
                        '1K-blocks': comps[1],
                        'used': comps[2],
                        'available': comps[3],
                        'capacity': comps[4],
                }
        except IndexError:
            log.error('Problem parsing disk usage information')
            ret = {}
    return ret


def inodeusage(args=None):
    '''
    Return inode usage information for volumes mounted on this minion

    CLI Example:

    .. code-block:: bash

        salt '*' disk.inodeusage
    '''
    flags = _clean_flags(args, 'disk.inodeusage')
    cmd = 'df -iP'
    if flags:
        cmd += ' -{0}'.format(flags)
    ret = {}
    out = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    for line in out:
        if line.startswith('Filesystem'):
            continue
        comps = line.split()
        # Don't choke on empty lines
        if not comps:
            continue

        try:
            if __grains__['kernel'] == 'OpenBSD':
                ret[comps[8]] = {
                    'inodes': int(comps[5]) + int(comps[6]),
                    'used': comps[5],
                    'free': comps[6],
                    'use': comps[7],
                    'filesystem': comps[0],
                }
            else:
                ret[comps[5]] = {
                    'inodes': comps[1],
                    'used': comps[2],
                    'free': comps[3],
                    'use': comps[4],
                    'filesystem': comps[0],
                }
        except (IndexError, ValueError):
            log.error('Problem parsing inode usage information')
            ret = {}
    return ret


def percent(args=None):
    '''
    Return partition information for volumes mounted on this minion

    CLI Example:

    .. code-block:: bash

        salt '*' disk.percent /var
    '''
    if __grains__['kernel'] == 'Linux':
        cmd = 'df -P'
    elif __grains__['kernel'] == 'OpenBSD':
        cmd = 'df -kP'
    else:
        cmd = 'df'
    ret = {}
    out = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    for line in out:
        if not line:
            continue
        if line.startswith('Filesystem'):
            continue
        comps = line.split()
        while not comps[1].isdigit():
            comps[0] = '{0} {1}'.format(comps[0], comps[1])
            comps.pop(1)
        try:
            if __grains__['kernel'] == 'Darwin':
                ret[comps[8]] = comps[4]
            else:
                ret[comps[5]] = comps[4]
        except IndexError:
            log.error('Problem parsing disk usage information')
            ret = {}
    if args and args not in ret:
        log.error('Problem parsing disk usage information: Partition \'{0}\' does not exist!'.format(args))
        ret = {}
    elif args:
        return ret[args]

    return ret


@decorators.which('blkid')
def blkid(device=None):
    '''
    Return block device attributes: UUID, LABEL, etc. This function only works
    on systems where blkid is available.

    CLI Example:

    .. code-block:: bash

        salt '*' disk.blkid
        salt '*' disk.blkid /dev/sda
    '''
    args = ""
    if device:
        args = " " + device

    ret = {}
    blkid_result = __salt__['cmd.run_all']('blkid' + args, python_shell=False)

    if blkid_result['retcode'] > 0:
        return ret

    for line in blkid_result['stdout'].splitlines():
        if not line:
            continue
        comps = line.split()
        device = comps[0][:-1]
        info = {}
        device_attributes = re.split(('\"*\"'), line.partition(' ')[2])
        for key, value in zip(*[iter(device_attributes)]*2):
            key = key.strip('=').strip(' ')
            info[key] = value.strip('"')
        ret[device] = info

    return ret


def tune(device, **kwargs):
    '''
    Set attributes for the specified device

    CLI Example:

    .. code-block:: bash

        salt '*' disk.tune /dev/sda1 read-ahead=1024 read-write=True

    Valid options are: ``read-ahead``, ``filesystem-read-ahead``,
    ``read-only``, ``read-write``.

    See the ``blockdev(8)`` manpage for a more complete description of these
    options.
    '''

    kwarg_map = {'read-ahead': 'setra',
                 'filesystem-read-ahead': 'setfra',
                 'read-only': 'setro',
                 'read-write': 'setrw'}
    opts = ''
    args = []
    for key in kwargs:
        if key in kwarg_map:
            switch = kwarg_map[key]
            if key != 'read-write':
                args.append(switch.replace('set', 'get'))
            else:
                args.append('getro')
            if kwargs[key] == 'True' or kwargs[key] is True:
                opts += '--{0} '.format(key)
            else:
                opts += '--{0} {1} '.format(switch, kwargs[key])
    cmd = 'blockdev {0}{1}'.format(opts, device)
    out = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    return dump(device, args)


def wipe(device):
    '''
    Remove the filesystem information

    CLI Example:

    .. code-block:: bash

        salt '*' disk.wipe /dev/sda1
    '''

    cmd = 'wipefs {0}'.format(device)
    try:
        out = __salt__['cmd.run_all'](cmd, python_shell=False)
    except subprocess.CalledProcessError as err:
        return False
    if out['retcode'] == 0:
        return True


def dump(device, args=None):
    '''
    Return all contents of dumpe2fs for a specified device

    CLI Example:
    .. code-block:: bash

        salt '*' disk.dump /dev/sda1
    '''
    cmd = 'blockdev --getro --getsz --getss --getpbsz --getiomin --getioopt --getalignoff ' \
          '--getmaxsect --getsize --getsize64 --getra --getfra {0}'.format(device)
    ret = {}
    opts = [c[2:] for c in cmd.split() if c.startswith('--')]
    out = __salt__['cmd.run_all'](cmd, python_shell=False)
    if out['retcode'] == 0:
        lines = [line for line in out['stdout'].splitlines() if line]
        count = 0
        for line in lines:
            ret[opts[count]] = line
            count = count+1
        if args:
            temp_ret = {}
            for arg in args:
                temp_ret[arg] = ret[arg]
            return temp_ret
        else:
            return ret
    else:
        return False


def resize2fs(device):
    '''
    Resizes the filesystem.

    CLI Example:
    .. code-block:: bash

        salt '*' disk.resize2fs /dev/sda1
    '''
    ret = {}
    cmd = 'resize2fs {0}'.format(device)
    try:
        out = __salt__['cmd.run_all'](cmd, python_shell=False)
    except subprocess.CalledProcessError as err:
        return False
    if out['retcode'] == 0:
        return True


@depends(HAS_HDPARM)
def _hdparm(args, failhard=True):
    '''
    Execute hdparm
    Fail hard when required
    return output when possible
    '''
    cmd = 'hdparm {0}'.format(args)
    result = __salt__['cmd.run_all'](cmd)
    if result['retcode'] != 0:
        msg = '{0}: {1}'.format(cmd, result['stderr'])
        if failhard:
            raise CommandExecutionError(msg)
        else:
            log.warning(msg)

    return result['stdout']


@depends(HAS_HDPARM)
def hdparms(disks, args=None):
    '''
    Retrieve all info's for all disks
    parse 'em into a nice dict
    (which, considering hdparms output, is quite a hassle)

    .. versionadded:: 2016.3.0

    CLI Example:
    .. code-block:: bash

        salt '*' disk.hdparms /dev/sda
    '''
    all_parms = 'aAbBcCdgHiJkMmNnQrRuW'
    if args is None:
        args = all_parms
    elif isinstance(args, (list, tuple)):
        args = ''.join(args)

    if not isinstance(disks, (list, tuple)):
        disks = [disks]

    out = {}
    for disk in disks:
        if not disk.startswith('/dev'):
            disk = '/dev/{0}'.format(disk)
        disk_data = {}
        for line in _hdparm('-{0} {1}'.format(args, disk), False).splitlines():
            line = line.strip()
            if len(line) == 0 or line == disk + ':':
                continue

            if ':' in line:
                key, vals = line.split(':', 1)
                key = re.sub(r' is$', '', key)
            elif '=' in line:
                key, vals = line.split('=', 1)
            else:
                continue
            key = key.strip().lower().replace(' ', '_')
            vals = vals.strip()

            rvals = []
            if re.match(r'[0-9]+ \(.*\)', vals):
                vals = vals.split(' ')
                rvals.append(int(vals[0]))
                rvals.append(vals[1].strip('()'))
            else:
                valdict = {}
                for val in re.split(r'[/,]', vals.strip()):
                    val = val.strip()
                    try:
                        val = int(val)
                        rvals.append(val)
                    except:  # pylint: disable=bare-except
                        if '=' in val:
                            deep_key, val = val.split('=', 1)
                            deep_key = deep_key.strip()
                            val = val.strip()
                            if len(val):
                                valdict[deep_key] = val
                        elif len(val):
                            rvals.append(val)
                if len(valdict):
                    rvals.append(valdict)
                if len(rvals) == 0:
                    continue
                elif len(rvals) == 1:
                    rvals = rvals[0]
            disk_data[key] = rvals

        out[disk] = disk_data

    return out


@depends(HAS_HDPARM)
def hpa(disks, size=None):
    '''
    Get/set Host Protected Area settings

    T13 INCITS 346-2001 (1367D) defines the BEER (Boot Engineering Extension Record)
    and PARTIES (Protected Area Run Time Interface Extension Services), allowing
    for a Host Protected Area on a disk.

    It's often used by OEMS to hide parts of a disk, and for overprovisioning SSD's

    .. warning::
        Setting the HPA might clobber your data, be very careful with this on active disks!

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' disk.hpa /dev/sda
        salt '*' disk.hpa /dev/sda 5%
        salt '*' disk.hpa /dev/sda 10543256
    '''

    hpa_data = {}
    for disk, data in hdparms(disks, 'N').items():
        visible, total, status = data.values()[0]
        if visible == total or 'disabled' in status:
            hpa_data[disk] = {
                'total': total
            }
        else:
            hpa_data[disk] = {
                'total': total,
                'visible': visible,
                'hidden': total - visible
            }

    if size is None:
        return hpa_data

    for disk, data in hpa_data.items():
        try:
            size = data['total'] - int(size)
        except:  # pylint: disable=bare-except
            if '%' in size:
                size = int(size.strip('%'))
                size = (100 - size) * data['total']
                size /= 100
        if size <= 0:
            size = data['total']

        _hdparm('--yes-i-know-what-i-am-doing -Np{0} {1}'.format(size, disk))


def smart_attributes(dev, attributes=None, values=None):
    '''
    Fetch SMART attributes
    Providing attributes will deliver only requested attributes
    Providing values will deliver only requested values for attributes

    Default is the Backblaze recommended
    set (https://www.backblaze.com/blog/hard-drive-smart-stats/):
    (5,187,188,197,198)

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' disk.smart_attributes /dev/sda
        salt '*' disk.smart_attributes /dev/sda attributes=(5,187,188,197,198)
    '''

    if not dev.startswith('/dev/'):
        dev = '/dev/' + dev

    cmd = 'smartctl --attributes {0}'.format(dev)
    smart_result = __salt__['cmd.run_all'](cmd, output_loglevel='quiet')
    if smart_result['retcode'] != 0:
        raise CommandExecutionError(smart_result['stderr'])

    smart_result = iter(smart_result['stdout'].splitlines())

    fields = []
    for line in smart_result:
        if line.startswith('ID#'):
            fields = re.split(r'\s+', line.strip())
            fields = [key.lower() for key in fields[1:]]
            break

    if values is not None:
        fields = [field if field in values else '_' for field in fields]

    smart_attr = {}
    for line in smart_result:
        if not re.match(r'[\s]*\d', line):
            break

        line = re.split(r'\s+', line.strip(), maxsplit=len(fields))
        attr = int(line[0])

        if attributes is not None and attr not in attributes:
            continue

        data = dict(zip(fields, line[1:]))
        try:
            del data['_']
        except:  # pylint: disable=bare-except
            pass

        for field in data.keys():
            val = data[field]
            try:
                val = int(val)
            except:  # pylint: disable=bare-except
                try:
                    val = [int(value) for value in val.split(' ')]
                except:  # pylint: disable=bare-except
                    pass
            data[field] = val

        smart_attr[attr] = data

    return smart_attr


@depends(HAS_IOSTAT)
def iostat(interval=1, count=5, disks=None):
    '''
    Gather and return (averaged) IO stats.

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' disk.iostat 1 5 disks=sda
    '''
    if salt.utils.is_linux():
        return _iostat_linux(interval, count, disks)
    elif salt.utils.is_freebsd():
        return _iostat_fbsd(interval, count, disks)


def _iostats_dict(header, stats):
    '''
    Transpose collected data, average it, stomp it in dict using header

    Use Decimals so we can properly calc & round, convert to float 'caus' we can't transmit Decimals over 0mq
    '''
    stats = [float((sum(stat) / len(stat)).quantize(decimal.Decimal('.01'))) for stat in zip(*stats)]
    stats = dict(zip(header, stats))
    return stats


def _iostat_fbsd(interval, count, disks):
    '''
    Tested on FreeBSD, quite likely other BSD's only need small changes in cmd syntax
    '''
    if disks is None:
        iostat_cmd = 'iostat -xC -w {0} -c {1} '.format(interval, count)
    elif isinstance(disks, six.string_types):
        iostat_cmd = 'iostat -x -w {0} -c {1} {2}'.format(interval, count, disks)
    else:
        iostat_cmd = 'iostat -x -w {0} -c {1} {2}'.format(interval, count, ' '.join(disks))

    sys_stats = []
    dev_stats = collections.defaultdict(list)
    sys_header = []
    dev_header = []
    h_len = 1000  # randomly absurdly high

    ret = iter(__salt__['cmd.run_stdout'](iostat_cmd, output_loglevel='quiet').splitlines())
    for line in ret:
        if not line.startswith('device'):
            continue
        elif not len(dev_header):
            dev_header = line.split()[1:]
        while line is not False:
            line = next(ret, False)
            if not line or not line[0].isalnum():
                break
            line = line.split()
            disk = line[0]
            stats = [decimal.Decimal(x) for x in line[1:]]
            # h_len will become smallest number of fields in stat lines
            if len(stats) < h_len:
                h_len = len(stats)
            dev_stats[disk].append(stats)

    iostats = {}

    # The header was longer than the smallest number of fields
    # Therefore the sys stats are hidden in there
    if h_len < len(dev_header):
        sys_header = dev_header[h_len:]
        dev_header = dev_header[0:h_len]

        for disk, stats in dev_stats.items():
            if len(stats[0]) > h_len:
                sys_stats = [stat[h_len:] for stat in stats]
                dev_stats[disk] = [stat[0:h_len] for stat in stats]

        iostats['sys'] = _iostats_dict(sys_header, sys_stats)

    for disk, stats in dev_stats.items():
        iostats[disk] = _iostats_dict(dev_header, stats)

    return iostats


def _iostat_linux(interval, count, disks):
    if disks is None:
        iostat_cmd = 'iostat -x {0} {1} '.format(interval, count)
    elif isinstance(disks, six.string_types):
        iostat_cmd = 'iostat -xd {0} {1} {2}'.format(interval, count, disks)
    else:
        iostat_cmd = 'iostat -xd {0} {1} {2}'.format(interval, count, ' '.join(disks))

    sys_stats = []
    dev_stats = collections.defaultdict(list)
    sys_header = []
    dev_header = []

    ret = iter(__salt__['cmd.run_stdout'](iostat_cmd, output_loglevel='quiet').splitlines())
    for line in ret:
        if line.startswith('avg-cpu:'):
            if not len(sys_header):
                sys_header = tuple(line.split()[1:])
            line = [decimal.Decimal(x) for x in next(ret).split()]
            sys_stats.append(line)
        elif line.startswith('Device:'):
            if not len(dev_header):
                dev_header = tuple(line.split()[1:])
            while line is not False:
                line = next(ret, False)
                if not line or not line[0].isalnum():
                    break
                line = line.split()
                disk = line[0]
                stats = [decimal.Decimal(x) for x in line[1:]]
                dev_stats[disk].append(stats)

    iostats = {}

    if len(sys_header):
        iostats['sys'] = _iostats_dict(sys_header, sys_stats)

    for disk, stats in dev_stats.items():
        iostats[disk] = _iostats_dict(dev_header, stats)

    return iostats
