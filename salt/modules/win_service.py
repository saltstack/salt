# -*- coding: utf-8 -*-
'''
Windows Service module.
'''

# Import python libs
from __future__ import absolute_import
import os
import salt.utils
import time
import logging
from salt.ext.six.moves import zip
from salt.ext.six.moves import range
from salt.exceptions import CommandExecutionError

# Import 3rd party libs
try:
    import win32api
    import win32con
    import win32security
    import win32service
    import win32serviceutil
    import pywintypes
    HAS_WIN32_MODS = True
except ImportError:
    HAS_WIN32_MODS = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'service'

SERVICE_TYPE = {1: 'Kernel Driver',
                2: 'File System Driver',
                4: 'Adapter Driver',
                8: 'Recognizer Driver',
                16: 'Win32 Own Process',
                32: 'Win32 Share Process',
                256: 'Interactive'}

SERVICE_CONTROLS = {1: 'Stop',
                    2: 'Pause/Continue',
                    4: 'Shutdown',
                    8: 'Change Parameters',
                    16: 'Netbind Change',
                    32: 'Hardware Profile Change',
                    64: 'Power Event',
                    128: 'Session Change',
                    256: 'Pre-Shutdown',
                    512: 'Time Change',
                    1024: 'Trigger Event'}

SERVICE_STATE = {1: 'Stopped',
                 2: 'Start Pending',
                 3: 'Stop Pending',
                 4: 'Running',
                 5: 'Continue Pending',
                 6: 'Pause Pending',
                 7: 'Paused'}

SERVICE_ERRORS = {0: 'No Error',
                  1066: 'Service Specific Error'}

SERVICE_START_TYPE = {'auto': 2,
                      'manual': 3,
                      'disabled': 4,
                      0: 'Boot',
                      1: 'System',
                      2: 'Auto',
                      3: 'Manual',
                      4: 'Disabled'}

SERVICE_ERROR_CONTROL = {0: 'Ignore',
                         1: 'Normal',
                         2: 'Severe',
                         3: 'Critical',
                         'ignore': 0,
                         'normal': 1,
                         'severe': 2,
                         'critical': 3}

BUFFSIZE = 5000
SERVICE_START_STOP_ATTEMPTS = 90


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if not salt.utils.is_windows():
        return (False, 'Module win_service: module only works on Windows.')
    if not HAS_WIN32_MODS:
        return (False, 'Module win_service: failed to load win32 modules')
    return __virtualname__


def get_enabled():
    '''
    Return the enabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    raw_services = _get_services()
    services = set()
    for service in raw_services:
        if info(service['ServiceName'])['StartType'] in ['Auto']:
            services.add(service['ServiceName'])

    return sorted(services)


def get_disabled():
    '''
    Return the disabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    raw_services = _get_services()
    services = set()
    for service in raw_services:
        if info(service['ServiceName'])['StartType'] in ['Manual', 'Disabled']:
            services.add(service['ServiceName'])

    return sorted(services)


def available(name):
    '''
    Returns ``True`` if the specified service is available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available <service name>
    '''
    return name in get_all()


def missing(name):
    '''
    The inverse of service.available.
    Returns ``True`` if the specified service is not available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing <service name>
    '''
    return name not in get_all()


def _get_services():
    handle_scm = win32service.OpenSCManager(
        None, None, win32service.SC_MANAGER_ENUMERATE_SERVICE)

    try:
        services = win32service.EnumServicesStatusEx(handle_scm)
    except AttributeError:
        services = win32service.EnumServicesStatus(handle_scm)
    finally:
        win32service.CloseServiceHandle(handle_scm)

    return services


def get_all():
    '''
    Return all installed services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    services = _get_services()

    ret = set()
    for service in services:
        ret.add(service['ServiceName'])

    return sorted(ret)


def get_service_name(*args):
    '''
    The Display Name is what is displayed in Windows when services.msc is
    executed.  Each Display Name has an associated Service Name which is the
    actual name of the service.  This function allows you to discover the
    Service Name by returning a dictionary of Display Names and Service Names,
    or filter by adding arguments of Display Names.

    If no args are passed, return a dict of all services where the keys are the
    service Display Names and the values are the Service Names.

    If arguments are passed, create a dict of Display Names and Service Names

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_service_name
        salt '*' service.get_service_name 'Google Update Service (gupdate)' 'DHCP Client'
    '''
    raw_services = _get_services()

    services = dict()
    for raw_service in raw_services:
        if args:
            if raw_service['DisplayName'] in args:
                services[raw_service['DisplayName']] = raw_service['ServiceName']
        else:
            services[raw_service['DisplayName']] = raw_service['ServiceName']

    return services


def _open_service_handles(name):
    handle_scm = win32service.OpenSCManager(
        None, None, win32service.SC_MANAGER_CONNECT)

    try:
        handle_svc = win32service.OpenService(
            handle_scm, name, win32service.SERVICE_ENUMERATE_DEPENDENTS |
            win32service.SERVICE_INTERROGATE |
            win32service.SERVICE_QUERY_CONFIG |
            win32service.SERVICE_QUERY_STATUS)
    except pywintypes.error as exc:
        raise CommandExecutionError('Failed Open {0}: {1}'.format(name, exc[2]))

    return handle_scm, handle_svc


def _close_service_handles(handle_scm, handle_svc):
    win32service.CloseServiceHandle(handle_scm)
    win32service.CloseServiceHandle(handle_svc)


def info(name):
    handle_scm, handle_svc = _open_service_handles(name)

    try:
        config_info = win32service.QueryServiceConfig(handle_svc)
        status_info = win32service.QueryServiceStatusEx(handle_svc)
        description = win32service.QueryServiceConfig2(
            handle_svc, win32service.SERVICE_CONFIG_DESCRIPTION)
        delayed_start = win32service.QueryServiceConfig2(
            handle_svc, win32service.SERVICE_CONFIG_DELAYED_AUTO_START_INFO)
    finally:
        _close_service_handles(handle_scm, handle_svc)

    sid = win32security.LookupAccountName('', 'NT Service\\{0}'.format(name))[0]

    ret = dict()
    ret['BinaryPath'] = config_info[3]
    ret['LoadOrderGroup'] = config_info[4]
    ret['TagID'] = config_info[5]
    ret['Dependencies'] = config_info[6]
    ret['ServiceAccount'] = config_info[7]
    ret['DisplayName'] = config_info[8]
    ret['Description'] = description
    ret['sid'] = win32security.ConvertSidToStringSid(sid)
    ret['Status_ServiceCode'] = status_info['ServiceSpecificExitCode']
    ret['Status_CheckPoint'] = status_info['CheckPoint']
    ret['Status_WaitHint'] = status_info['WaitHint']
    ret['StartTypeDelayed'] = delayed_start

    flags = list()
    for bit in SERVICE_TYPE:
        if config_info[0] & bit:
            flags.append(SERVICE_TYPE[bit])

    ret['ServiceType'] = flags if flags else config_info[0]

    flags = list()
    for bit in SERVICE_CONTROLS:
        if status_info['ControlsAccepted'] & bit:
            flags.append(SERVICE_CONTROLS[bit])

    ret['ControlsAccepted'] = flags if flags else status_info['ControlsAccepted']

    try:
        ret['Status_ExitCode'] = SERVICE_ERRORS[status_info['Win32ExitCode']]
    except KeyError:
        ret['Status_ExitCode'] = status_info['Win32ExitCode']

    try:
        ret['StartType'] = SERVICE_START_TYPE[config_info[1]]
    except KeyError:
        ret['StartType'] = config_info[1]

    try:
        ret['ErrorControl'] = SERVICE_ERROR_CONTROL[config_info[2]]
    except KeyError:
        ret['ErrorControl'] = config_info[2]

    try:
        ret['Status'] = SERVICE_STATE[status_info['CurrentState']]
    except KeyError:
        ret['Status'] = status_info['CurrentState']

    return ret


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    if status(name):
        return True

    win32serviceutil.StartService(name)

    attempts = 0
    while info(name)['Status'] in ['Start Pending'] \
            and attempts <= SERVICE_START_STOP_ATTEMPTS:
        time.sleep(1)

    return status(name)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    if not status(name):
        return True

    win32serviceutil.StopService(name)

    attempts = 0
    while info(name)['Status'] in ['Stop Pending'] \
            and attempts <= SERVICE_START_STOP_ATTEMPTS:
        time.sleep(1)

    return not status(name)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    if 'salt-minion' in name:
        create_win_salt_restart_task()
        return execute_salt_restart_task()

    return stop(name) and start(name)


def create_win_salt_restart_task():
    '''
    Create a task in Windows task scheduler to enable restarting the salt-minion

    CLI Example:

    .. code-block:: bash

        salt '*' service.create_win_salt_restart_task()
    '''
    cmd = 'cmd'
    args = '/c ping -n 3 127.0.0.1 && net stop salt-minion && net start salt-minion'
    return __salt__['task.create_task'](name='restart-salt-minion',
                                        user_name='System',
                                        force=True,
                                        action_type='Execute',
                                        cmd=cmd,
                                        arguments=args,
                                        trigger_type='Once',
                                        start_date='1975-01-01',
                                        start_time='01:00')


def execute_salt_restart_task():
    '''
    Run the Windows Salt restart task

    CLI Example:

    .. code-block:: bash

        salt '*' service.execute_salt_restart_task()
    '''
    return __salt__['task.run'](name='restart-salt-minion')


def status(name, sig=None):
    '''
    Return the status for a service, returns the PID or an empty string if the
    service is running or not, pass a signature to use to find the service via
    ps

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name> [service signature]
    '''
    if info(name)['Status'] in ['Running', 'Stop Pending']:
        return True

    return False


def getsid(name):
    '''
    Return the sid for this windows service

    CLI Example:

    .. code-block:: bash

        salt '*' service.getsid <service name>
    '''
    return info['sid']


def modify(name,
           bin_path=None,  # str
           exe_args=None,  # str
           display_name=None,  # str
           description=None,  # str
           service_type=None,  # ????
           start_type=None,  # auto, manual, disabled
           start_delayed=None,  # bool
           error_control=None,  # ignore, normal, severe, critical
           load_order_group=None,  # str, ''
           dependencies=None,  # list, ''
           account_name=None,  # NT Service\<service name>, <domain>\<service name>, LocalSystem, LocalService, NetworkService
           account_password=None,  # str, '' for ^
           run_interactive=None):  # Bool
    # https://msdn.microsoft.com/en-us/library/windows/desktop/ms681987(v=vs.85).aspx
    # https://msdn.microsoft.com/en-us/library/windows/desktop/ms681988(v-vs.85).aspx

    handle_scm = win32service.OpenSCManager(
        None, None, win32service.SC_MANAGER_CONNECT)

    try:
        handle_svc = win32service.OpenService(
            handle_scm, name, win32service.SERVICE_ALL_ACCESS)
    except pywintypes.error as exc:
        raise CommandExecutionError('Failed Open {0}: {1}'.format(name, exc[2]))

    config_info = win32service.QueryServiceConfig(handle_svc)

    changes = dict()

    # Input Validation
    if bin_path is not None:
        bin_path = bin_path.strip('"')
        if exe_args is not None:
            bin_path = '{0} {1}'.format(bin_path, exe_args)
        changes['BinaryPath'] = bin_path

    if service_type is not None:
        if service_type.lower() in SERVICE_TYPE:
            service_type = SERVICE_TYPE[service_type.lower()]
            if run_interactive:
                service_type = service_type | \
                               win32service.SERVICE_INTERACTIVE_PROCESS
        else:
            raise CommandExecutionError(
                'Invalid Service Type: {0}'.format(service_type))
    else:
        if run_interactive is True:
            service_type = config_info[0] | \
                           win32service.SERVICE_INTERACTIVE_PROCESS
        elif run_interactive is False:
            service_type = config_info[0] ^ \
                           win32service.SERVICE_INTERACTIVE_PROCESS
        else:
            service_type = win32service.SERVICE_NO_CHANGE

    if service_type is not win32service.SERVICE_NO_CHANGE:
        flags = list()
        for bit in SERVICE_TYPE:
            if service_type & bit:
                flags.append(SERVICE_TYPE[bit])

        changes['ServiceType'] = flags if flags else service_type

    if start_type is not None:
        if start_type.lower() in SERVICE_START_TYPE:
            start_type = SERVICE_START_TYPE[start_type.lower()]
        else:
            raise CommandExecutionError(
                'Invalid Start Type: {0}'.format(start_type))
        changes['StartType'] = SERVICE_START_TYPE[start_type]
    else:
        start_type = win32service.SERVICE_NO_CHANGE

    if error_control is not None:
        if error_control.lower() in SERVICE_START_TYPE:
            error_control = SERVICE_START_TYPE[error_control.lower()]
        else:
            raise CommandExecutionError(
                'Invalid Error Control: {0}'.format(error_control))
        changes['ErrorControl'] = SERVICE_ERROR_CONTROL[error_control]

    else:
        error_control = win32service.SERVICE_NO_CHANGE

    if account_name is not None:
        changes['ServiceAccount'] = account_name
    if account_name in ['LocalSystem', 'NetworkService', 'LocalSystem']:
        account_password = ''

    if account_password is not None:
        changes['ServiceAccountPassword'] = 'XXX-REDACTED-XXX'

    if load_order_group is not None:
        changes['LoadOrderGroup'] = load_order_group

    if dependencies is not None:
        changes['Dependencies'] = dependencies

    if display_name is not None:
        changes['DisplayName'] = display_name

    win32service.ChangeServiceConfig(handle_svc,
                                     service_type,
                                     start_type,
                                     error_control,
                                     bin_path,
                                     load_order_group,
                                     0,
                                     dependencies,
                                     account_name,
                                     account_password,
                                     display_name)

    if description is not None:
        win32service.ChangeServiceConfig2(
            handle_svc, win32service.SERVICE_CONFIG_DESCRIPTION, description)
        changes['Description'] = description

    if start_delayed is not None:
        # You can only set delayed start for services that are set to auto start
        # Start type 2 is Auto
        # Start type -1 is no change
        if (start_type == -1 and config_info[1] == 2) or start_type == 2:
            win32service.ChangeServiceConfig2(
                handle_svc, win32service.SERVICE_CONFIG_DELAYED_AUTO_START_INFO,
                start_delayed)
            changes['StartTypeDelayed'] = start_delayed
        else:
            changes['Warning'] = 'start_delayed: Requires start_type "auto"'

    _close_service_handles(handle_scm, handle_svc)

    return changes


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    '''
    cmd = ['sc', 'config', name, 'start=', 'auto']
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    cmd = ['sc', 'config', name, 'start=', 'disabled']
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def enabled(name, **kwargs):
    '''
    Check to see if the named service is enabled to start on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    '''
    cmd = ['sc', 'qc', name]
    lines = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    for line in lines:
        if 'AUTO_START' in line:
            return True
    return False


def disabled(name):
    '''
    Check to see if the named service is disabled to start on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    '''
    cmd = ['sc', 'qc', name]
    lines = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    for line in lines:
        if 'DEMAND_START' in line:
            return True
        elif 'DISABLED' in line:
            return True
    return False


def create(name,
           binpath,
           DisplayName=None,
           type='own',
           start='demand',
           error='normal',
           group=None,
           tag='no',
           depend=None,
           obj=None,
           password=None,
           **kwargs):
    r'''
    Create the named service.

    .. versionadded:: 2015.8.0

    Required parameters:

    :param name: Specifies the service name returned by the getkeyname operation

    :param binpath: Specifies the path to the service binary file, backslashes must be escaped
      - eg: C:\\path\\to\\binary.exe

    Optional parameters:

    :param DisplayName: the name to be displayed in the service manager

    :param type: Specifies the service type, default is own
      - own (default): Service runs in its own process
      - share: Service runs as a shared process
      - interact: Service can interact with the desktop
      - kernel: Service is a driver
      - filesys: Service is a system driver
      - rec: Service is a file system-recognized driver that identifies filesystems on the computer

    :param start: Specifies the start type for the service
      - boot: Device driver that is loaded by the boot loader
      - system: Device driver that is started during kernel initialization
      - auto: Service that automatically starts
      - demand (default): Service must be started manually
      - disabled: Service cannot be started
      - delayed-auto: Service starts automatically after other auto-services start

    :param error: Specifies the severity of the error
      - normal (default): Error is logged and a message box is displayed
      - severe: Error is logged and computer attempts a restart with last known good configuration
      - critical: Error is logged, computer attempts to restart with last known good configuration, system halts on failure
      - ignore: Error is logged and startup continues, no notification is given to the user

    :param group: Specifies the name of the group of which this service is a member

    :param tag: Specifies whether or not to obtain a TagID from the CreateService call. For boot-start and system-start drivers
      - yes/no

    :param depend: Specifies the names of services or groups that myust start before this service. The names are separated by forward slashes.

    :param obj: Specifies the name of an account in which a service will run. Default is LocalSystem

    :param password: Specifies a password. Required if other than LocalSystem account is used.

    CLI Example:

    .. code-block:: bash

        salt '*' service.create <service name> <path to exe> display_name='<display name>'
    '''

    cmd = [
           'sc',
           'create',
           name,
           'binpath=', binpath,
           'type=', type,
           'start=', start,
           'error=', error,
           ]
    if DisplayName is not None:
        cmd.extend(['DisplayName=', DisplayName])
    if group is not None:
        cmd.extend(['group=', group])
    if depend is not None:
        cmd.extend(['depend=', depend])
    if obj is not None:
        cmd.extend(['obj=', obj])
    if password is not None:
        cmd.extend(['password=', password])

    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def config(name,
           bin_path=None,
           display_name=None,
           svc_type=None,
           start_type=None,
           error=None,
           group=None,
           tag=None,
           depend=None,
           obj=None,
           password=None,
           **kwargs):
    r'''
    Modify the named service.

    .. versionadded:: 2015.8.8

    Required parameters:

    :param str name: Specifies the service name returned by the getkeyname
    operation


    Optional parameters:

    :param str bin_path: Specifies the path to the service binary file,
    backslashes must be escaped
    - eg: C:\\path\\to\\binary.exe

    :param str display_name: the name to be displayed in the service manager
    Specifies a more descriptive name for identifying the service in user
    interface programs.

    :param str svc_type: Specifies the service type. Acceptable values are:
      - own (default): Service runs in its own process
      - share: Service runs as a shared process
      - interact: Service can interact with the desktop
      - kernel: Service is a driver
      - filesys: Service is a system driver
      - rec: Service is a file system-recognized driver that identifies
        filesystems on the computer
      - adapt: Service is an adapter driver that identifies hardware such as
        keyboards, mice and disk drives

    :param str start_type: Specifies the start type for the service.
    Acceptable values are:
      - boot: Device driver that is loaded by the boot loader
      - system: Device driver that is started during kernel initialization
      - auto: Service that automatically starts
      - demand (default): Service must be started manually
      - disabled: Service cannot be started
      - delayed-auto: Service starts automatically after other auto-services
        start

    :param str error: Specifies the severity of the error if the service
    fails to start. Acceptable values are:
      - normal (default): Error is logged and a message box is displayed
      - severe: Error is logged and computer attempts a restart with last known
        good configuration
      - critical: Error is logged, computer attempts to restart with last known
        good configuration, system halts on failure
      - ignore: Error is logged and startup continues, no notification is given
        to the user

    :param str group: Specifies the name of the group of which this service is a
    member. The list of groups is stored in the registry, in the
    HKLM\System\CurrentControlSet\Control\ServiceGroupOrder subkey. The default
    is null.

    :param str tag: Specifies whether or not to obtain a TagID from the
    CreateService call. For boot-start and system-start drivers only.
    Acceptable values are:
      - yes/no

    :param str depend: Specifies the names of services or groups that must start
    before this service. The names are separated by forward slashes.

    :param str obj: Specifies the name of an account in which a service will run
    or specifies a name of the Windows driver object in which the driver will
    run. Default is LocalSystem

    :param str password: Specifies a password. Required if other than
    LocalSystem account is used.

    :return: True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' service.config <service name> <path to exe> display_name='<display name>'
    '''

    cmd = ['sc', 'config', name]
    if bin_path is not None:
        cmd.extend(['binpath=', bin_path])
    if svc_type is not None:
        cmd.extend(['type=', svc_type])
    if start_type is not None:
        cmd.extend(['start=', start_type])
    if error is not None:
        cmd.extend(['error=', error])
    if display_name is not None:
        cmd.extend(['DisplayName=', display_name])
    if group is not None:
        cmd.extend(['group=', group])
    if tag is not None:
        cmd.extend(['tag=', tag])
    if depend is not None:
        cmd.extend(['depend=', depend])
    if obj is not None:
        cmd.extend(['obj=', obj])
    if password is not None:
        cmd.extend(['password=', password])

    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def delete(name):
    '''
    Delete the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.delete <service name>
    '''
    cmd = ['sc', 'delete', name]
    return not __salt__['cmd.retcode'](cmd, python_shell=False)
