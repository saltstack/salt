# -*- coding: utf-8 -*-
'''
Module for returning various status data about a minion.
These data can be useful for compiling into stats later.
'''


# Import python libs
from __future__ import absolute_import
import os
import re
import fnmatch
import collections
import time
import datetime

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import range  # pylint: disable=import-error,no-name-in-module,redefined-builtin

# Import salt libs
import salt.config
import salt.utils
import salt.utils.event
from salt.utils.network import host_to_ip as _host_to_ip
from salt.utils.network import remote_port_tcp as _remote_port_tcp
from salt.ext.six.moves import zip
from salt.utils.decorators import with_deprecated
from salt.exceptions import CommandExecutionError

__virtualname__ = 'status'
__opts__ = {}


def __virtual__():
    if salt.utils.is_windows():
        return False, 'Windows platform is not supported by this module'

    return __virtualname__


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
    for key, val in six.iteritems(conf):
        func = '{0}()'.format(key.split('.')[1])
        vals = eval(func)  # pylint: disable=W0123

        for item in val:
            ret[item] = vals[item]

    return ret


@with_deprecated(globals(), "Boron")
def uptime():
    '''
    Return the uptime for this system.

    CLI Example:

    .. code-block:: bash

        salt '*' status.uptime
    '''
    ut_path = "/proc/uptime"
    if not os.path.exists(ut_path):
        raise CommandExecutionError("File {ut_path} was not found.".format(ut_path=ut_path))

    ut_ret = {
        'seconds': int(float(open(ut_path).read().strip().split()[0]))
    }

    utc_time = datetime.datetime.utcfromtimestamp(time.time() - ut_ret['seconds'])
    ut_ret['since_iso'] = utc_time.isoformat()
    ut_ret['since_t'] = time.mktime(utc_time.timetuple())
    ut_ret['days'] = ut_ret['seconds'] / 60 / 60 / 24
    hours = (ut_ret['seconds'] - (ut_ret['days'] * 24 * 60 * 60)) / 60 / 60
    minutes = ((ut_ret['seconds'] - (ut_ret['days'] * 24 * 60 * 60)) / 60) - hours * 60
    ut_ret['time'] = '{0}:{1}'.format(hours, minutes)
    ut_ret['users'] = len(__salt__['cmd.run']("who -s").split(os.linesep))

    return ut_ret


def _uptime(human_readable=True):
    '''
    Return the uptime for this minion

    human_readable: True
        If ``True`` return the output provided by the system.  If ``False``
        return the output in seconds.

        .. versionadded:: 2015.8.4

    CLI Example:

    .. code-block:: bash

        salt '*' status.uptime
    '''
    if human_readable:
        return __salt__['cmd.run']('uptime')
    else:
        if os.path.exists('/proc/uptime'):
            out = __salt__['cmd.run']('cat /proc/uptime').split()
            if len(out):
                return out[0]
            else:
                return 'unexpected format in /proc/uptime'
        return 'cannot find /proc/uptime'


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
    def linux_cpustats():
        '''
        linux specific implementation of cpustats
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

    def freebsd_cpustats():
        '''
        freebsd specific implementation of cpustats
        '''
        vmstat = __salt__['cmd.run']('vmstat -P').splitlines()
        vm0 = vmstat[0].split()
        cpu0loc = vm0.index('cpu0')
        vm1 = vmstat[1].split()
        usloc = vm1.index('us')
        vm2 = vmstat[2].split()
        cpuctr = 0
        ret = {}
        for cpu in vm0[cpu0loc:]:
            ret[cpu] = {'us': _number(vm2[usloc + 3 * cpuctr]),
                        'sy': _number(vm2[usloc + 1 + 3 * cpuctr]),
                        'id': _number(vm2[usloc + 2 + 3 * cpuctr]), }
            cpuctr += 1
        return ret

    # dict that return a function that does the right thing per platform
    get_version = {
        'Linux': linux_cpustats,
        'FreeBSD': freebsd_cpustats,
    }

    errmsg = 'This method is unsupported on the current operating system!'
    return get_version.get(__grains__['kernel'], lambda: errmsg)()


def meminfo():
    '''
    Return the memory info for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.meminfo
    '''
    def linux_meminfo():
        '''
        linux specific implementation of meminfo
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

    def freebsd_meminfo():
        '''
        freebsd specific implementation of meminfo
        '''
        sysctlvm = __salt__['cmd.run']('sysctl vm').splitlines()
        sysctlvm = [x for x in sysctlvm if x.startswith('vm')]
        sysctlvm = [x.split(':') for x in sysctlvm]
        sysctlvm = [[y.strip() for y in x] for x in sysctlvm]
        sysctlvm = [x for x in sysctlvm if x[1]]  # If x[1] not empty

        ret = {}
        for line in sysctlvm:
            ret[line[0]] = line[1]
        # Special handling for vm.total as it's especially important
        sysctlvmtot = __salt__['cmd.run']('sysctl -n vm.vmtotal').splitlines()
        sysctlvmtot = [x for x in sysctlvmtot if x]
        ret['vm.vmtotal'] = sysctlvmtot
        return ret
    # dict that return a function that does the right thing per platform
    get_version = {
        'Linux': linux_meminfo,
        'FreeBSD': freebsd_meminfo,
    }

    errmsg = 'This method is unsupported on the current operating system!'
    return get_version.get(__grains__['kernel'], lambda: errmsg)()


def cpuinfo():
    '''
    Return the CPU info for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.cpuinfo
    '''
    def linux_cpuinfo():
        '''
        linux specific cpuinfo implementation
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

    def freebsd_cpuinfo():
        '''
        freebsd specific cpuinfo implementation
        '''
        freebsd_cmd = 'sysctl hw.model hw.ncpu'
        ret = {}
        for line in __salt__['cmd.run'](freebsd_cmd).splitlines():
            if not line:
                continue
            comps = line.split(':')
            comps[0] = comps[0].strip()
            ret[comps[0]] = comps[1].strip()
        return ret

    # dict that returns a function that does the right thing per platform
    get_version = {
        'Linux': linux_cpuinfo,
        'FreeBSD': freebsd_cpuinfo,
    }

    errmsg = 'This method is unsupported on the current operating system!'
    return get_version.get(__grains__['kernel'], lambda: errmsg)()


def diskstats():
    '''
    Return the disk stats for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.diskstats
    '''
    def linux_diskstats():
        '''
        linux specific implementation of diskstats
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

    def freebsd_diskstats():
        '''
        freebsd specific implementation of diskstats
        '''
        ret = {}
        iostat = __salt__['cmd.run']('iostat -xzd').splitlines()
        header = iostat[1]
        for line in iostat[2:]:
            comps = line.split()
            ret[comps[0]] = {}
            for metric, value in zip(header.split()[1:], comps[1:]):
                ret[comps[0]][metric] = _number(value)
        return ret

    # dict that return a function that does the right thing per platform
    get_version = {
        'Linux': linux_diskstats,
        'FreeBSD': freebsd_diskstats,
    }

    errmsg = 'This method is unsupported on the current operating system!'
    return get_version.get(__grains__['kernel'], lambda: errmsg)()


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
        # ifile source of data varies with OS, otherwise all the same
        if __grains__['kernel'] == 'Linux':
            procf = '/proc/mounts'
            if not os.path.isfile(procf):
                return {}
            ifile = salt.utils.fopen(procf, 'r').readlines()
        elif __grains__['kernel'] == 'FreeBSD':
            ifile = __salt__['cmd.run']('mount -p').splitlines()

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
    def linux_vmstats():
        '''
        linux specific implementation of vmstats
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

    def freebsd_vmstats():
        '''
        freebsd specific implementation of vmstats
        '''
        ret = {}
        for line in __salt__['cmd.run']('vmstat -s').splitlines():
            comps = line.split()
            if comps[0].isdigit():
                ret[' '.join(comps[1:])] = _number(comps[0])
        return ret
    # dict that returns a function that does the right thing per platform
    get_version = {
        'Linux': linux_vmstats,
        'FreeBSD': freebsd_vmstats,
    }

    errmsg = 'This method is unsupported on the current operating system!'
    return get_version.get(__grains__['kernel'], lambda: errmsg)()


def nproc():
    '''
    Return the number of processing units available on this system

    CLI Example:

    .. code-block:: bash

        salt '*' status.nproc
    '''
    try:
        return int(__salt__['cmd.run']('nproc').strip())
    except ValueError:
        return 0


def netstats():
    '''
    Return the network stats for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.netstats
    '''
    def linux_netstats():
        '''
        freebsd specific netstats implementation
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

    def freebsd_netstats():
        '''
        freebsd specific netstats implementation
        '''
        ret = {}
        for line in __salt__['cmd.run']('netstat -s').splitlines():
            if line.startswith('\t\t'):
                continue  # Skip, too detailed
            if not line.startswith('\t'):
                key = line.split()[0]
                ret[key] = {}
            else:
                comps = line.split()
                if comps[0].isdigit():
                    ret[key][' '.join(comps[1:])] = comps[0]
        return ret

    # dict that returns a function that does the right thing per platform
    get_version = {
        'Linux': linux_netstats,
        'FreeBSD': freebsd_netstats,
    }

    errmsg = 'This method is unsupported on the current operating system!'
    return get_version.get(__grains__['kernel'], lambda: errmsg)()


def netdev():
    '''
    Return the network device stats for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.netdev
    '''
    def linux_netdev():
        '''
        linux specific implementation of netdev
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
            # Support lines both like eth0:999 and eth0: 9999
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

    def freebsd_netdev():
        '''
        freebsd specific implementation of netdev
        '''
        _dict_tree = lambda: collections.defaultdict(_dict_tree)
        ret = _dict_tree()
        netstat = __salt__['cmd.run']('netstat -i -n -4 -b -d').splitlines()
        netstat += __salt__['cmd.run']('netstat -i -n -6 -b -d').splitlines()[1:]
        header = netstat[0].split()
        for line in netstat[1:]:
            comps = line.split()
            for i in range(4, 13):  # The columns we want
                ret[comps[0]][comps[2]][comps[3]][header[i]] = _number(comps[i])
        return ret
    # dict that returns a function that does the right thing per platform
    get_version = {
        'Linux': linux_netdev,
        'FreeBSD': freebsd_netdev,
    }

    errmsg = 'This method is unsupported on the current operating system!'
    return get_version.get(__grains__['kernel'], lambda: errmsg)()


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
    Pass a signature to use to find the process via ps.  Note you can pass
    a Python-compatible regular expression to return all pids of
    processes matching the regexp.

    CLI Example:

    .. code-block:: bash

        salt '*' status.pid <sig>
    '''

    cmd = __grains__['ps']
    output = __salt__['cmd.run_stdout'](cmd)

    pids = ''
    for line in output.splitlines():
        if 'status.pid' in line:
            continue
        if re.search(sig, line):
            if pids:
                pids += '\n'
            pids += line.split()[1]

    return pids


def version():
    '''
    Return the system version for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.version
    '''
    def linux_version():
        '''
        linux specific implementation of version
        '''
        procf = '/proc/version'
        if not os.path.isfile(procf):
            return {}
        return salt.utils.fopen(procf, 'r').read().strip()

    # dict that returns a function that does the right thing per platform
    get_version = {
        'Linux': linux_version,
        'FreeBSD': lambda: __salt__['cmd.run']('sysctl -n kern.version'),
    }

    errmsg = 'This method is unsupported on the current operating system!'
    return get_version.get(__grains__['kernel'], lambda: errmsg)()


def master(master=None, connected=True):
    '''
    .. versionadded:: 2014.7.0

    Fire an event if the minion gets disconnected from its master. This
    function is meant to be run via a scheduled job from the minion. If
    master_ip is an FQDN/Hostname, is must be resolvable to a valid IPv4
    address.

    CLI Example:

    .. code-block:: bash

        salt '*' status.master
    '''

    # the default publishing port
    port = 4505
    master_ip = None

    if __salt__['config.get']('publish_port') != '':
        port = int(__salt__['config.get']('publish_port'))

    # Check if we have FQDN/hostname defined as master
    # address and try resolving it first. _remote_port_tcp
    # only works with IP-addresses.
    if master is not None:
        tmp_ip = _host_to_ip(master)
        if tmp_ip is not None:
            master_ip = tmp_ip

    ips = _remote_port_tcp(port)

    if connected:
        if master_ip not in ips:
            event = salt.utils.event.get_event('minion', opts=__opts__, listen=False)
            event.fire_event({'master': master}, '__master_disconnected')
    else:
        if master_ip in ips:
            event = salt.utils.event.get_event('minion', opts=__opts__, listen=False)
            event.fire_event({'master': master}, '__master_connected')
