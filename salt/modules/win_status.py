# -*- coding: utf-8 -*-
'''
Module for returning various status data about a minion.
These data can be useful for compiling into stats later,
or for problem solving if your minion is having problems.

.. versionadded:: 0.12.0

:depends:   - pythoncom
            - wmi
'''

# Import Python Libs
from __future__ import absolute_import
import os
import ctypes
import sys
import time
import datetime
import logging

log = logging.getLogger(__name__)

# Import Salt Libs
import salt.utils
import salt.ext.six as six
import salt.utils.event
from salt._compat import subprocess
from salt.utils.network import host_to_ips as _host_to_ips
# pylint: disable=W0611
from salt.modules.status import ping_master, time_
import copy
# pylint: enable=W0611
from salt.utils import namespaced_function as _namespaced_function

# Import 3rd Party Libs
if salt.utils.is_windows():
    import wmi
    import salt.utils.winapi
    HAS_WMI = True
else:
    HAS_WMI = False

__opts__ = {}
__virtualname__ = 'status'


def __virtual__():
    '''
    Only works on Windows systems with WMI and WinAPI
    '''
    if not salt.utils.is_windows():
        return False, 'win_status.py: Requires Windows'

    if not HAS_WMI:
        return False, 'win_status.py: Requires WMI and WinAPI'

    # Namespace modules from `status.py`
    global ping_master, time_
    ping_master = _namespaced_function(ping_master, globals())
    time_ = _namespaced_function(time_, globals())

    return __virtualname__

__func_alias__ = {
    'time_': 'time'
}


def cpuload():
    '''
    .. versionadded:: 2015.8.0

    Return the processor load as a percentage

    CLI Example:

    .. code-block:: bash

       salt '*' status.cpuload
    '''

    # Pull in the information from WMIC
    cmd = ['wmic', 'cpu', 'get', 'loadpercentage', '/value']
    return int(__salt__['cmd.run'](cmd).split('=')[1])


def diskusage(human_readable=False, path=None):
    '''
    .. versionadded:: 2015.8.0

    Return the disk usage for this minion

    human_readable : False
        If ``True``, usage will be in KB/MB/GB etc.

    CLI Example:

    .. code-block:: bash

        salt '*' status.diskusage path=c:/salt
    '''
    if not path:
        path = 'c:/'

    # Credit for the source and ideas for this function:
    # http://code.activestate.com/recipes/577972-disk-usage/?in=user-4178764
    _, total, free = \
        ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_longlong()
    if sys.version_info >= (3, ) or isinstance(path, six.text_type):
        fun = ctypes.windll.kernel32.GetDiskFreeSpaceExw
    else:
        fun = ctypes.windll.kernel32.GetDiskFreeSpaceExA
    ret = fun(path, ctypes.byref(_), ctypes.byref(total), ctypes.byref(free))
    if ret == 0:
        raise ctypes.WinError()
    used = total.value - free.value

    total_val = total.value
    used_val = used
    free_val = free.value

    if human_readable:
        total_val = _byte_calc(total_val)
        used_val = _byte_calc(used_val)
        free_val = _byte_calc(free_val)

    return {'total': total_val, 'used': used_val, 'free': free_val}


def procs(count=False):
    '''
    Return the process data

    count : False
        If ``True``, this function will simply return the number of processes.

        .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' status.procs
        salt '*' status.procs count
    '''
    with salt.utils.winapi.Com():
        wmi_obj = wmi.WMI()
        processes = wmi_obj.win32_process()

    #this short circuit's the function to get a short simple proc count.
    if count:
        return len(processes)

    #a propper run of the function, creating a nonsensically long out put.
    process_info = {}
    for proc in processes:
        process_info[proc.ProcessId] = _get_process_info(proc)

    return process_info


def saltmem(human_readable=False):
    '''
    .. versionadded:: 2015.8.0

    Returns the amount of memory that salt is using

    human_readable : False
        return the value in a nicely formatted number

    CLI Example:

    .. code-block:: bash

        salt '*' status.saltmem
        salt '*' status.saltmem human_readable=True
    '''
    with salt.utils.winapi.Com():
        wmi_obj = wmi.WMI()
        result = wmi_obj.query(
            'SELECT WorkingSet FROM Win32_PerfRawData_PerfProc_Process '
            'WHERE IDProcess={0}'.format(os.getpid())
        )
        mem = int(result[0].wmi_property('WorkingSet').value)
        if human_readable:
            return _byte_calc(mem)
        return mem


def uptime(human_readable=False):
    '''
    .. versionadded:: 2015.8.0

    Return the system uptime for this machine in seconds

    human_readable : False
        If ``True``, then return uptime in years, days, and seconds.

    CLI Example:

    .. code-block:: bash

       salt '*' status.uptime
       salt '*' status.uptime human_readable=True
    '''

    # Open up a subprocess to get information from WMIC
    cmd = ['wmic', 'os', 'get', 'lastbootuptime', '/value']
    startup_time = __salt__['cmd.run'](cmd).split('=')[1][:14]

    # Convert to time struct
    startup_time = time.strptime(startup_time, '%Y%m%d%H%M%S')
    # Convert to datetime object
    startup_time = datetime.datetime(*startup_time[:6])

    # Subtract startup time from current time to get the uptime of the system
    uptime = datetime.datetime.now() - startup_time

    return str(uptime) if human_readable else uptime.total_seconds()


def _get_process_info(proc):
    '''
    Return  process information
    '''
    cmd = salt.utils.to_str(proc.CommandLine or '')
    name = salt.utils.to_str(proc.Name)
    info = dict(
        cmd=cmd,
        name=name,
        **_get_process_owner(proc)
    )
    return info


def _get_process_owner(process):
    owner = {}
    domain, error_code, user = None, None, None
    try:
        domain, error_code, user = process.GetOwner()
        owner['user'] = salt.utils.to_str(user)
        owner['user_domain'] = salt.utils.to_str(domain)
    except Exception as exc:
        pass
    if not error_code and all((user, domain)):
        owner['user'] = salt.utils.to_str(user)
        owner['user_domain'] = salt.utils.to_str(domain)
    elif process.ProcessId in [0, 4] and error_code == 2:
        # Access Denied for System Idle Process and System
        owner['user'] = 'SYSTEM'
        owner['user_domain'] = 'NT AUTHORITY'
    else:
        log.warning('Error getting owner of process; PID=\'{0}\'; Error: {1}'
                    .format(process.ProcessId, error_code))
    return owner


def _byte_calc(val):
    if val < 1024:
        tstr = str(val)+'B'
    elif val < 1038336:
        tstr = str(val/1024)+'KB'
    elif val < 1073741824:
        tstr = str(val/1038336)+'MB'
    elif val < 1099511627776:
        tstr = str(val/1073741824)+'GB'
    else:
        tstr = str(val/1099511627776)+'TB'
    return tstr


def master(master=None, connected=True):
    '''
    .. versionadded:: 2015.5.0

    Fire an event if the minion gets disconnected from its master. This
    function is meant to be run via a scheduled job from the minion. If
    master_ip is an FQDN/Hostname, is must be resolvable to a valid IPv4
    address.

    CLI Example:

    .. code-block:: bash

        salt '*' status.master
    '''

    def _win_remotes_on(port):
        '''
        Windows specific helper function.
        Returns set of ipv4 host addresses of remote established connections
        on local or remote tcp port.

        Parses output of shell 'netstat' to get connections

        PS C:> netstat -n -p TCP

        Active Connections

          Proto  Local Address          Foreign Address        State
          TCP    10.1.1.26:3389         10.1.1.1:4505          ESTABLISHED
          TCP    10.1.1.26:56862        10.1.1.10:49155        TIME_WAIT
          TCP    10.1.1.26:56868        169.254.169.254:80     CLOSE_WAIT
          TCP    127.0.0.1:49197        127.0.0.1:49198        ESTABLISHED
          TCP    127.0.0.1:49198        127.0.0.1:49197        ESTABLISHED
        '''
        remotes = set()
        try:
            data = subprocess.check_output(['netstat', '-n', '-p', 'TCP'])  # pylint: disable=minimum-python-version
        except subprocess.CalledProcessError:
            log.error('Failed netstat')
            raise

        lines = salt.utils.to_str(data).split('\n')
        for line in lines:
            if 'ESTABLISHED' not in line:
                continue
            chunks = line.split()
            remote_host, remote_port = chunks[2].rsplit(':', 1)
            if int(remote_port) != port:
                continue
            remotes.add(remote_host)
        return remotes

    # the default publishing port
    port = 4505
    master_ips = None

    if master:
        master_ips = _host_to_ips(master)

    if not master_ips:
        return

    if __salt__['config.get']('publish_port') != '':
        port = int(__salt__['config.get']('publish_port'))

    master_connection_status = False
    connected_ips = _win_remotes_on(port)

    # Get connection status for master
    for master_ip in master_ips:
        if master_ip in connected_ips:
            master_connection_status = True
            break

    # Connection to master is not as expected
    if master_connection_status is not connected:
        event = salt.utils.event.get_event('minion', opts=__opts__, listen=False)
        if master_connection_status:
            event.fire_event({'master': master}, salt.minion.master_event(type='connected'))
        else:
            event.fire_event({'master': master}, salt.minion.master_event(type='disconnected'))

    return master_connection_status
