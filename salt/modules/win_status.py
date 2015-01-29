# -*- coding: utf-8 -*-
'''
Module for returning various status data about a minion.
These data can be useful for compiling into stats later,
or for problem solving if your minion is having problems.

:depends:   - pythoncom
            - wmi
'''
from __future__ import absolute_import

import logging
import salt.utils

import os
import ctypes
import sys
import collections
import subprocess

log = logging.getLogger(__name__)

try:
    import wmi
    import salt.utils.winapi
    has_required_packages = True
except ImportError:
    if salt.utils.is_windows():
        log.exception('pywin32 and wmi python packages are required '
                      'in order to use the status module.')
    has_required_packages = False


__opts__ = {}

# Define the module's virtual name
__virtualname__ = 'status'


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows() and has_required_packages:
        return __virtualname__
    return False


def procs(count=False):
    '''
    Return the process data
    for quick use, the argument count tells you how many processes there are.

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

def cpu_load():
    '''
    Return the processor load as a percentage.

    CLI Example:

    .. code-block:: bash

       salt '*' status.cpu_load
    '''

    #open up a subprocess to get information from WMIC
    proc = subprocess.Popen('wmic cpu',stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    #pull in the information from WMIC
    outs = proc.communicate()

    #split that out the information into tuples.
    info = outs[0].split('\n')

    #find the location of LoadPercentage
    column = info[0].index('LoadPercentage')

    #get the end of the number.
    end = info[1].index(' ',column+1)

    #return pull it out of the informatin and cast it to an int.
    return int(info[1][column:end])

def disk_usage(human_readable=False,path=None):
    '''
    return the disk usage for this minion

    CLI Example:

    .. code-block:: bash

        salt '*' status.disk_usage path=c:/salt

    '''

    if not path:
        path = 'c:/'

    #Credit for the source and ideas for this function:
    # http://code.activestate.com/recipes/577972-disk-usage/?in=user-4178764
    _, total, free = ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_longlong()
    if sys.version_info >= (3,) or isinstance(path,unicode):
        fun = ctypes.windll.kernel32.GetDiskFreeSpaceExw
    else:
        fun = ctypes.windll.kernel32.GetDiskFreeSpaceExA
    ret = fun(path, ctypes.byref(_), ctypes.byref(total), ctypes.byref(free))
    if ret == 0 :
        raise ctypes.WinError()
    used = total.value - free.value

    if human_readable:
        tstr = _byte_calc(total.value)
        ustr = _byte_calc(used)
        fstr = _byte_calc(free.value)
        return 'Total: {0}, Used: {1}, Free: {2}'.format(tstr,ustr,fstr)
    else:
        return {'total':total.value,'used':used,'free':free.value}

def salt_mem(human_readable=False):
    '''
    Returns the amount of memory that salt is using.

    human_readable: return the value in a nicely formated number.

    CLI Example:

    .. code-black:: bash

        salt '*' status.salt_mem
        salt '*' status.salt_mem human_readable
    '''
    with salt.utils.winapi.Com():
        wmi_obj = wmi.WMI()
        result = wmi_obj.query('SELECT WorkingSet FROM Win32_PerfRawData_PerfProc_Process WHERE IDProcess={0}'.format(os.getpid()))
        mem = int(result[0].wmi_property('WorkingSet').value)
        if human_readable:
            if mem < 1024:
                return str(mem)+'B'
            elif mem < 1038336:
                return str(mem/1024)+'kB'
            else:
                return str(mem/1038336)+'MB'
        return mem

def _get_process_info(proc):
    '''
    Return  process information
    '''
    cmd = (proc.CommandLine or '').encode('utf-8')
    name = proc.Name.encode('utf-8')
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
        owner['user'] = user.encode('utf-8')
        owner['user_domain'] = domain.encode('utf-8')
    except Exception as exc:
        pass
    if not error_code and all((user, domain)):
        owner['user'] = user.encode('utf-8')
        owner['user_domain'] = domain.encode('utf-8')
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
            tstr = str(val/1024)+'kB'
        elif val < 1073741824:
            tstr = str(val/1038336)+'MB'
        elif val < 1099511627776:
            tstr = str(val/1073741824)+'GB'
        else:
            tstr = str(val/1099511627776)+'TB'
        return tstr
