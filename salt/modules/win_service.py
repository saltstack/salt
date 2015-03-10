# -*- coding: utf-8 -*-
'''
Windows Service module.
'''

# Import python libs
import salt.utils
import time
import logging
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

    if has_powershell():
        cmd = 'Get-WmiObject win32_service | where {$_.startmode -eq "Auto"} | select-object name'
        lines = __salt__['cmd.run'](cmd, shell='POWERSHELL', python_shell=True).splitlines()
        return sorted([line.strip() for line in lines[3:]])
    else:
        ret = set()
        services = []
        cmd = ['sc', 'query', 'type=', 'service', 'state=', 'all', 'bufsize=', str(BUFFSIZE)]
        lines = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
        for line in lines:
            if 'SERVICE_NAME:' in line:
                comps = line.split(':', 1)
                if not len(comps) > 1:
                    continue
                services.append(comps[1].strip())
        for service in services:
            cmd2 = ['sc', 'qc', service, str(BUFFSIZE)]
            lines = __salt__['cmd.run'](cmd2, python_shell=False).splitlines()
            for line in lines:
                if 'AUTO_START' in line:
                    ret.add(service)
        return sorted(ret)


def get_disabled():
    '''
    Return the disabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    if has_powershell():
        cmd = 'Get-WmiObject win32_service | where {$_.startmode -ne "Auto"} | select-object name'
        lines = __salt__['cmd.run'](cmd, shell='POWERSHELL', python_shell=True).splitlines()
        return sorted([line.strip() for line in lines[3:]])
    else:
        ret = set()
        services = []
        cmd = ['sc', 'query', 'type=', 'service', 'state=', 'all', 'bufsize=', str(BUFFSIZE)]
        lines = __salt__['cmd.run'](cmd, python_shell=False).splitlines()
        for line in lines:
            if 'SERVICE_NAME:' in line:
                comps = line.split(':', 1)
                if not len(comps) > 1:
                    continue
                services.append(comps[1].strip())
        for service in services:
            cmd2 = ['sc', 'qc', service, BUFFSIZE]
            lines = __salt__['cmd.run'](cmd2, python_shell=False).splitlines()
            for line in lines:
                if 'DEMAND_START' in line:
                    ret.add(service)
                elif 'DISABLED' in line:
                    ret.add(service)
        return sorted(ret)


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
    return sorted(get_enabled() + get_disabled())


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
        cmd = 'Restart-Service {0}'.format(_cmd_quote(name))
        return not __salt__['cmd.retcode'](cmd, shell='powershell', python_shell=True)
    return stop(name) and start(name)


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
            if comps[1] > 1:
                return comps[1].strip()
            else:
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


def enabled(name):
    '''
    Check to see if the named service is enabled to start on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    '''
    return name in get_enabled()


def disabled(name):
    '''
    Check to see if the named service is disabled to start on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    '''
    return name in get_disabled()
