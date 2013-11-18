# -*- coding: utf-8 -*-
'''
Windows Service module.
'''

# Import python libs
import time
import salt.utils

# Define the module's virtual name
__virtualname__ = 'service'

BUFFSIZE = 5000


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False


def get_enabled():
    '''
    Return the enabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    ret = set()
    services = []
    cmd = 'sc query type= service state= all bufsize= {0}'.format(BUFFSIZE)
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        if 'SERVICE_NAME:' in line:
            comps = line.split(':', 1)
            if not len(comps) > 1:
                continue
            services.append(comps[1].strip())
    for service in services:
        cmd2 = 'sc qc "{0}" {1}'.format(service, BUFFSIZE)
        lines = __salt__['cmd.run'](cmd2).splitlines()
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
    ret = set()
    services = []
    cmd = 'sc query type= service state= all bufsize= {0}'.format(BUFFSIZE)
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        if 'SERVICE_NAME:' in line:
            comps = line.split(':', 1)
            if not len(comps) > 1:
                continue
            services.append(comps[1].strip())
    for service in services:
        cmd2 = 'sc qc "{0}" {1}'.format(service, BUFFSIZE)
        lines = __salt__['cmd.run'](cmd2).splitlines()
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
    return not name in get_all()


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
    cmd = 'sc query type= service state= all bufsize= {0}'.format(BUFFSIZE)
    lines = __salt__['cmd.run'](cmd).splitlines()
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
    cmd = 'sc start "{0}"'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = 'sc stop "{0}"'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    stop(name)
    for idx in xrange(5):
        if status(name):
            time.sleep(2)
            continue
        return start(name)
    return False


def status(name, sig=None):
    '''
    Return the status for a service, returns the PID or an empty string if the
    service is running or not, pass a signature to use to find the service via
    ps

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name> [service signature]
    '''
    cmd = 'sc query "{0}" {1}'.format(name, BUFFSIZE)
    statuses = __salt__['cmd.run'](cmd).splitlines()
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
    cmd = 'sc showsid "{0}"'.format(name)
    lines = __salt__['cmd.run'](cmd).splitlines()
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
    cmd = 'sc config "{0}" start= auto'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    cmd = 'sc config "{0}" start= demand'.format(name)
    return not __salt__['cmd.retcode'](cmd)


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
