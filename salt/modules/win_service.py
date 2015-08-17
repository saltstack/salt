# -*- coding: utf-8 -*-
'''
Windows Service module.
'''

# Import python libs
from __future__ import absolute_import
import salt.utils
import time
import logging
from subprocess import list2cmdline
from salt.ext.six.moves import zip
from salt.ext.six.moves import range
try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote

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
    return False


def has_powershell():
    '''
    Confirm if Powershell is available

    CLI Example:

    .. code-block:: bash

        salt '*' service.has_powershell
    '''
    return 'powershell' in __salt__['cmd.run'](
            ['where', 'powershell'], python_shell=False
        )


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
    cmd = list2cmdline(['sc', 'query', 'type=', 'service', 'state=', 'all', 'bufsize=', str(BUFFSIZE)])
    lines = __salt__['cmd.run'](cmd).splitlines()
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
    if has_powershell():
        if 'salt-minion' in name:
            create_win_salt_restart_task()
            return execute_salt_restart_task()
        cmd = 'Restart-Service {0}'.format(_cmd_quote(name))
        return not __salt__['cmd.retcode'](cmd, shell='powershell', python_shell=True)
    return stop(name) and start(name)


def create_win_salt_restart_task():
    '''

    Create a task in Windows task scheduler to enable restarting the salt-minion

    CLI Example:

    .. code-block:: bash

        salt '*' service.create_win_salt_restart_task()
    '''
    cmd = 'schtasks /RU "System" /Create /TN restart-salt-minion /TR "powershell Restart-Service salt-minion" /sc ONCE /sd 01/01/1975 /st 01:00 /F /V1 /Z'

    return __salt__['cmd.shell'](cmd)


def execute_salt_restart_task():
    '''
    Run the Windows Salt restart task

    CLI Example:

    .. code-block:: bash

        salt '*' service.execute_salt_restart_task()
    '''
    cmd = 'schtasks /Run /TN restart-salt-minion'
    return __salt__['cmd.shell'](cmd)


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
    cmd = list2cmdline(['sc', 'qc', name])
    lines = __salt__['cmd.run'](cmd).splitlines()
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
    cmd = list2cmdline(['sc', 'qc', name])
    lines = __salt__['cmd.run'](cmd).splitlines()
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
    '''
    Create the named service.

    .. versionadded:: 2015.8.0

    Required parameters:
    name: Specifies the service name returned by the getkeyname operation
    binpath: Specifies the path to the service binary file, backslashes must be escaped
        - eg: C:\\path\\to\\binary.exe

    Optional parameters:
    DisplayName: the name to be displayed in the service manager
    type: Specifies the service type, default is own
      - own (default): Service runs in its own process
      - share: Service runs as a shared process
      - interact: Service can interact with the desktop
      - kernel: Service is a driver
      - filesys: Service is a system driver
      - rec: Service is a file system-recognized driver that identifies filesystems on the computer
    start: Specifies the start type for the service
      - boot: Device driver that is loaded by the boot loader
      - system: Device driver that is started during kernel initialization
      - auto: Service that automatically starts
      - demand (default): Service must be started manually
      - disabled: Service cannot be started
      - delayed-auto: Service starts automatically after other auto-services start
    error: Specifies the severity of the error
      - normal (default): Error is logged and a message box is displayed
      - severe: Error is logged and computer attempts a restart with last known good configuration
      - critical: Error is logged, computer attempts to restart with last known good configuration, system halts on failure
      - ignore: Error is logged and startup continues, no notification is given to the user
    group: Specifies the name of the group of which this service is a member
    tag: Specifies whether or not to obtain a TagID from the CreateService call. For boot-start and system-start drivers
      - yes/no
    depend: Specifies the names of services or groups that myust start before this service. The names are seperated by forward slashes.
    obj: Specifies th ename of an account in which a service will run. Default is LocalSystem
    password: Specifies a password. Required if other than LocalSystem account is used.

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


def delete(name):
    '''
    Delete the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.delete <service name>
    '''
    cmd = ['sc', 'delete', name]
    return not __salt__['cmd.retcode'](cmd, python_shell=False)
