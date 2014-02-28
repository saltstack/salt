# -*- coding: utf-8 -*-
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

# Don't shadow built-in's.
__func_alias__ = {
    'help_': 'help'
}


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows() and has_required_packages:
        return __virtualname__
    return False


def procs():
    '''
    Return the process data

    CLI Example:

    .. code-block:: bash

        salt '*' status.procs
    '''
    with salt.utils.winapi.Com():
        wmi_obj = wmi.WMI()
        processes = wmi_obj.win32_process()

        process_info = {}
        for proc in processes:
            process_info[proc.ProcessId] = _get_process_info(proc)

        return process_info


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


def help_(cmd=None):
    '''
    Display help for module

    CLI Example:

    .. code-block:: bash

        salt '*' status.help

        salt '*' status.help procs
    '''
    if '__virtualname__' in globals():
        module_name = __virtualname__
    else:
        module_name = __name__.split('.')[-1]

    if cmd is None:
        return __salt__['sys.doc']('{0}' . format(module_name))
    else:
        return __salt__['sys.doc']('{0}.{1}' . format(module_name, cmd))
