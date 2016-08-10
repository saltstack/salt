# -*- coding: utf-8 -*-
'''
Windows Service module.
'''

# Import python libs
from __future__ import absolute_import
import salt.utils
import time
import logging
from salt.ext.six.moves import zip
from salt.ext.six.moves import range

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'service'

BUFFSIZE = 5000
SERVICE_STOP_DELAY_SECONDS = 15
SERVICE_STOP_POLL_MAX_ATTEMPTS = 5


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return (False, "Module win_service: module only works on Windows systems")


def get_enabled():
    '''
    Return the enabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    return sorted([service for service in get_all() if enabled(service)])


def get_disabled():
    '''
    Return the disabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    return sorted([service for service in get_all() if disabled(service)])


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


def get_all():
    '''
    Return all installed services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    ret = set()
    cmd = ['sc', 'query', 'type=', 'service', 'state=', 'all', 'bufsize=', str(BUFFSIZE)]
    lines = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    for line in lines:
        if 'SERVICE_NAME:' in line:
            comps = line.split(':', 1)
            if not len(comps) > 1:
                continue
            ret.add(comps[1].strip())
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
    ret = {}
    services = []
    display_names = []
    cmd = ['sc', 'query', 'type=', 'service', 'state=', 'all', 'bufsize=', str(BUFFSIZE)]
    lines = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    for line in lines:
        if 'SERVICE_NAME:' in line:
            comps = line.split(':', 1)
            if not len(comps) > 1:
                continue
            services.append(comps[1].strip())
        if 'DISPLAY_NAME:' in line:
            comps = line.split(':', 1)
            if not len(comps) > 1:
                continue
            display_names.append(comps[1].strip())
    if len(services) == len(display_names):
        service_dict = dict(zip(display_names, services))
    else:
        return 'Service Names and Display Names mismatch'
    if len(args) == 0:
        return service_dict
    for arg in args:
        if arg in service_dict:
            ret[arg] = service_dict[arg]
    return ret


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    cmd = ['net', 'start', name]
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    # net stop issues a stop command and waits briefly (~30s), but will give
    # up if the service takes too long to stop with a misleading
    # "service could not be stopped" message and RC 0.

    cmd = ['net', 'stop', name]
    res = __salt__['cmd.run'](cmd, python_shell=False)
    if 'service was stopped' in res:
        return True

    # we requested a stop, but the service is still thinking about it.
    # poll for the real status
    for attempt in range(SERVICE_STOP_POLL_MAX_ATTEMPTS):
        if not status(name):
            return True
        log.debug('Waiting for %s to stop', name)
        time.sleep(SERVICE_STOP_DELAY_SECONDS)

    log.warning('Giving up on waiting for service `%s` to stop', name)
    return False


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
    cmd = ['sc', 'query', name]
    statuses = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    for line in statuses:
        if 'RUNNING' in line:
            return True
        elif 'STOP_PENDING' in line:
            return True
    return False


def getsid(name):
    '''
    Return the sid for this windows service

    CLI Example:

    .. code-block:: bash

        salt '*' service.getsid <service name>
    '''
    cmd = ['sc', 'showsid', name]
    lines = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
    for line in lines:
        if 'SERVICE SID:' in line:
            comps = line.split(':', 1)
            try:
                return comps[1].strip()
            except (AttributeError, IndexError):
                return None


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

    :param obj: Specifies th ename of an account in which a service will run. Default is LocalSystem

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

    :param str obj: Specifies th name of an account in which a service will run
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
