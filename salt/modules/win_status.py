'''
Module for returning various status data about a minion.
These data can be useful for compiling into stats later.

:depends:   - pythoncom
            - wmi
'''

import logging
import salt.utils


log = logging.getLogger(__name__)

try:
    import pythoncom
    import wmi
    has_required_packages = True
except ImportError:
    log.exception('pywin32 and wmi python packages are required '
                  'in order to use the status module.')
    has_required_packages = False


__opts__ = {}


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows() and has_required_packages:
        return 'status'
    return False


def procs():
    '''
    Return the process data

    CLI Example::

        salt '*' status.procs
    '''
    pythoncom.CoInitialize()  # need to call if not in main thread
    wmi_obj = wmi.WMI()
    processes = wmi_obj.win32_process()

    process_info = {}
    for proc in processes:
        process_info[proc.ProcessId] = _get_process_info(proc)

    return process_info


def _get_process_info(proc):
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
    domain, error_code, user = process.GetOwner()
    if not error_code:
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
