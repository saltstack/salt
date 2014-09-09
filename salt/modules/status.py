# -*- coding: utf-8 -*-
'''
Module for returning various status data about a minion.
These data can be useful for compiling into stats later.
'''

# Import python libs
import os
import re
import fnmatch

# Import salt libs
import salt.utils
from salt.utils.network import remote_port_tcp as _remote_port_tcp
import salt.utils.event
import salt.config


__opts__ = {}


# TODO: Make this module support windows hosts
# TODO: Make this module support BSD hosts properly, this is very Linux specific
def __virtual__():
    if salt.utils.is_windows():
        return False
    return True


def _number(text):
    '''
    Convert a string to a number.
    Returns an integer if the string represents an integer, a floating
    point number if the string is a real number, or the string unchanged
    otherwise.
    '''
    if text.isdigit():
        return int(text)
    try:
        return float(text)
    except ValueError:
        return text


def procs():
    '''
    Return the process data

    CLI Example:

    .. code-block:: bash

        salt '*' status.procs
    '''
    # Get the user, pid and cmd
    ret = {}
    uind = 0
    pind = 0
    cind = 0
    plines = __salt__['cmd.run'](__grains__['ps']).splitlines()
    guide = plines.pop(0).split()
    if 'USER' in guide:
        uind = guide.index('USER')
    elif 'UID' in guide:
        uind = guide.index('UID')
    if 'PID' in guide:
        pind = guide.index('PID')
    if 'COMMAND' in guide:
        cind = guide.index('COMMAND')
    elif 'CMD' in guide:
        cind = guide.index('CMD')
    for line in plines:
        if not line:
            continue
        comps = line.split()
        ret[comps[pind]] = {'user': comps[uind],
                            'cmd': ' '.join(comps[cind:])}
    return ret


def custom():
    '''
    Return a custom composite of status data and info for this minion,
    based on the minion config file. An example config like might be::

        status.cpustats.custom: [ 'cpu', 'ctxt', 'btime', 'processes' ]

    Where status refers to status.py, cpustats is the function
    where we get our data, and custom is this function It is followed
    by a list of keys that we want returned.

    This function is meant to replace all_status(), which returns
    anything and everything, which we probably don't want.

    By default, nothing is returned. Warning: Depending on what you
    include, there can be a LOT here!

    CLI Example:

    .. code-block:: bash

        salt '*' status.custom
    '''
    ret = {}
    conf = __salt__['config.dot_vals']('status')
    for key, val in conf.items():
        func = '{0}()'.format(key.split('.')[1])
        vals = eval(func)  # pylint: disable=W0123

        for item in val:
            ret[item] = vals[item]

    return ret


def uptime():
    '''
    Return the uptime for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.uptime
    '''
    return __salt__['cmd.run']('uptime')


def loadavg():
    '''
    Return the load averages for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.loadavg
    '''
    load_avg = os.getloadavg()
    return {'1-min': load_avg[0],
            '5-min': load_avg[1],
            '15-min': load_avg[2]}


def cpustats():
    '''
    Return the CPU stats for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.cpustats
    '''
    procf = '/proc/stat'
    if not os.path.isfile(procf):
        return {}
    stats = salt.utils.fopen(procf, 'r').read().splitlines()
    ret = {}
    for line in stats:
        if not line:
            continue
        comps = line.split()
        if comps[0] == 'cpu':
            ret[comps[0]] = {'idle': _number(comps[4]),
                             'iowait': _number(comps[5]),
                             'irq': _number(comps[6]),
                             'nice': _number(comps[2]),
                             'softirq': _number(comps[7]),
                             'steal': _number(comps[8]),
                             'system': _number(comps[3]),
                             'user': _number(comps[1])}
        elif comps[0] == 'intr':
            ret[comps[0]] = {'total': _number(comps[1]),
                             'irqs': [_number(x) for x in comps[2:]]}
        elif comps[0] == 'softirq':
            ret[comps[0]] = {'total': _number(comps[1]),
                             'softirqs': [_number(x) for x in comps[2:]]}
        else:
            ret[comps[0]] = _number(comps[1])
    return ret


def meminfo():
    '''
    Return the memory info for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.meminfo
    '''
    procf = '/proc/meminfo'
    if not os.path.isfile(procf):
        return {}
    stats = salt.utils.fopen(procf, 'r').read().splitlines()
    ret = {}
    for line in stats:
        if not line:
            continue
        comps = line.split()
        comps[0] = comps[0].replace(':', '')
        ret[comps[0]] = {
            'value': comps[1],
        }
        if len(comps) > 2:
            ret[comps[0]]['unit'] = comps[2]
    return ret


def cpuinfo():
    '''
    Return the CPU info for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.cpuinfo
    '''
    procf = '/proc/cpuinfo'
    if not os.path.isfile(procf):
        return {}
    stats = salt.utils.fopen(procf, 'r').read().splitlines()
    ret = {}
    for line in stats:
        if not line:
            continue
        comps = line.split(':')
        comps[0] = comps[0].strip()
        if comps[0] == 'flags':
            ret[comps[0]] = comps[1].split()
        else:
            ret[comps[0]] = comps[1].strip()
    return ret


def diskstats():
    '''
    Return the disk stats for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.diskstats
    '''
    procf = '/proc/diskstats'
    if not os.path.isfile(procf):
        return {}
    stats = salt.utils.fopen(procf, 'r').read().splitlines()
    ret = {}
    for line in stats:
        if not line:
            continue
        comps = line.split()
        ret[comps[2]] = {'major': _number(comps[0]),
                         'minor': _number(comps[1]),
                         'device': _number(comps[2]),
                         'reads_issued': _number(comps[3]),
                         'reads_merged': _number(comps[4]),
                         'sectors_read': _number(comps[5]),
                         'ms_spent_reading': _number(comps[6]),
                         'writes_completed': _number(comps[7]),
                         'writes_merged': _number(comps[8]),
                         'sectors_written': _number(comps[9]),
                         'ms_spent_writing': _number(comps[10]),
                         'io_in_progress': _number(comps[11]),
                         'ms_spent_in_io': _number(comps[12]),
                         'weighted_ms_spent_in_io': _number(comps[13])}
    return ret


def diskusage(*args):
    '''
    Return the disk usage for this minion

    Usage::

        salt '*' status.diskusage [paths and/or filesystem types]

    CLI Example:

    .. code-block:: bash

        salt '*' status.diskusage         # usage for all filesystems
        salt '*' status.diskusage / /tmp  # usage for / and /tmp
        salt '*' status.diskusage ext?    # usage for ext[234] filesystems
        salt '*' status.diskusage / ext?  # usage for / and all ext filesystems
    '''
    procf = '/proc/mounts'
    if not os.path.isfile(procf):
        return {}
    selected = set()
    fstypes = set()
    if not args:
        # select all filesystems
        fstypes.add('*')
    else:
        for arg in args:
            if arg.startswith('/'):
                # select path
                selected.add(arg)
            else:
                # select fstype
                fstypes.add(arg)

    if fstypes:
        # determine which mount points host the specified fstypes
        regex = re.compile(
            '|'.join(
                fnmatch.translate(fstype).format('(%s)') for fstype in fstypes
            )
        )
        with salt.utils.fopen(procf, 'r') as ifile:
            for line in ifile:
                comps = line.split()
                if len(comps) >= 3:
                    mntpt = comps[1]
                    fstype = comps[2]
                    if regex.match(fstype):
                        selected.add(mntpt)

    # query the filesystems disk usage
    ret = {}
    for path in selected:
        fsstats = os.statvfs(path)
        blksz = fsstats.f_bsize
        available = fsstats.f_bavail * blksz
        total = fsstats.f_blocks * blksz
        ret[path] = {"available": available, "total": total}
    return ret


def vmstats():
    '''
    Return the virtual memory stats for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.vmstats
    '''
    procf = '/proc/vmstat'
    if not os.path.isfile(procf):
        return {}
    stats = salt.utils.fopen(procf, 'r').read().splitlines()
    ret = {}
    for line in stats:
        if not line:
            continue
        comps = line.split()
        ret[comps[0]] = _number(comps[1])
    return ret


def nproc():
    '''
    Return the number of processing units available on this system

    CLI Example:

    .. code-block:: bash

        salt '*' status.nproc
    '''
    data = __salt__['cmd.run']('nproc')
    try:
        ret = int(data.strip())
    except Exception:
        return 0
    return ret


def netstats():
    '''
    Return the network stats for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.netstats
    '''
    procf = '/proc/net/netstat'
    if not os.path.isfile(procf):
        return {}
    stats = salt.utils.fopen(procf, 'r').read().splitlines()
    ret = {}
    headers = ['']
    for line in stats:
        if not line:
            continue
        comps = line.split()
        if comps[0] == headers[0]:
            index = len(headers) - 1
            row = {}
            for field in range(index):
                if field < 1:
                    continue
                else:
                    row[headers[field]] = _number(comps[field])
            rowname = headers[0].replace(':', '')
            ret[rowname] = row
        else:
            headers = comps
    return ret


def netdev():
    '''
    Return the network device stats for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.netdev
    '''
    procf = '/proc/net/dev'
    if not os.path.isfile(procf):
        return {}
    stats = salt.utils.fopen(procf, 'r').read().splitlines()
    ret = {}
    for line in stats:
        if not line:
            continue
        if line.find(':') < 0:
            continue
        comps = line.split()
        # Fix lines like eth0:9999..'
        comps[0] = line.split(':')[0].strip()
        #Support lines both like eth0:999 and eth0: 9999
        comps.insert(1, line.split(':')[1].strip().split()[0])
        ret[comps[0]] = {'iface': comps[0],
                         'rx_bytes': _number(comps[1]),
                         'rx_compressed': _number(comps[7]),
                         'rx_drop': _number(comps[4]),
                         'rx_errs': _number(comps[3]),
                         'rx_fifo': _number(comps[5]),
                         'rx_frame': _number(comps[6]),
                         'rx_multicast': _number(comps[8]),
                         'rx_packets': _number(comps[2]),
                         'tx_bytes': _number(comps[9]),
                         'tx_carrier': _number(comps[15]),
                         'tx_colls': _number(comps[14]),
                         'tx_compressed': _number(comps[16]),
                         'tx_drop': _number(comps[12]),
                         'tx_errs': _number(comps[11]),
                         'tx_fifo': _number(comps[13]),
                         'tx_packets': _number(comps[10])}
    return ret


def w():  # pylint: disable=C0103
    '''
    Return a list of logged in users for this minion, using the w command

    CLI Example:

    .. code-block:: bash

        salt '*' status.w
    '''
    user_list = []
    users = __salt__['cmd.run']('w -h').splitlines()
    for row in users:
        if not row:
            continue
        comps = row.split()
        rec = {'idle': comps[3],
               'jcpu': comps[4],
               'login': comps[2],
               'pcpu': comps[5],
               'tty': comps[1],
               'user': comps[0],
               'what': ' '.join(comps[6:])}
        user_list.append(rec)
    return user_list


def all_status():
    '''
    Return a composite of all status data and info for this minion.
    Warning: There is a LOT here!

    CLI Example:

    .. code-block:: bash

        salt '*' status.all_status
    '''
    return {'cpuinfo': cpuinfo(),
            'cpustats': cpustats(),
            'diskstats': diskstats(),
            'diskusage': diskusage(),
            'loadavg': loadavg(),
            'meminfo': meminfo(),
            'netdev': netdev(),
            'netstats': netstats(),
            'uptime': uptime(),
            'vmstats': vmstats(),
            'w': w()}


def pid(sig):
    '''
    Return the PID or an empty string if the process is running or not.
    Pass a signature to use to find the process via ps.

    CLI Example:

    .. code-block:: bash

        salt '*' status.pid <sig>
    '''
    # Check whether the sig is already quoted (we check at the end in case they
    # send a sig like `-E 'someregex'` to use egrep) and doesn't begin with a
    # dash (again, like `-E someregex`).  Quote sigs that qualify.
    if (not sig.endswith('"') and not sig.endswith("'") and
            not sig.startswith('-')):
        sig = "'" + sig + "'"
    cmd = ("{0[ps]} | grep {1} | grep -v grep | fgrep -v status.pid | "
           "awk '{{print $2}}'".format(__grains__, sig))
    return __salt__['cmd.run_stdout'](cmd) or ''


def version():
    '''
    Return the system version for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.version
    '''
    procf = '/proc/version'
    if not os.path.isfile(procf):
        return {}
    ret = salt.utils.fopen(procf, 'r').read().strip()

    return ret


def master(master_ip=None, connected=True):
    '''
    .. versionadded:: 2014.7.0

    Fire an event if the minion gets disconnected from its master. This
    function is meant to be run via a scheduled job from the minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.master
    '''
    port = int(__salt__['config.option']('publish_port'))
    ips = _remote_port_tcp(port)

    if connected:
        if master_ip not in ips:
            event = salt.utils.event.get_event('minion', opts=__opts__, listen=False)
            event.fire_event({'master': master_ip}, '__master_disconnected')
    else:
        if master_ip in ips:
            event = salt.utils.event.get_event('minion', opts=__opts__, listen=False)
            event.fire_event({'master': master_ip}, '__master_connected')
