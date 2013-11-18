# -*- coding: utf-8 -*-
'''
Service support for Solaris 10 and 11, should work with other systems
that use SMF also. (e.g. SmartOS)
'''

__func_alias__ = {
    'reload_': 'reload'
}

# Define the module's virtual name
__virtualname__ = 'service'


def __virtual__():
    '''
    Only work on systems which default to SMF
    '''
    # Don't let this work on Solaris 9 since SMF doesn't exist on it.
    enable = set((
        'Solaris',
        'SmartOS',
    ))
    if __grains__['os'] in enable:
        if __grains__['os'] == 'Solaris' and __grains__['kernelrelease'] == "5.9":
            return False
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
    cmd = 'svcs -H -o SVC,STATE -s SVC'
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        if 'online' in line:
            ret.add(comps[0])
    return sorted(ret)


def get_disabled():
    '''
    Return the disabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    ret = set()
    cmd = 'svcs -aH -o SVC,STATE -s SVC'
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        if not 'online' in line and not 'legacy_run' in line:
            ret.add(comps[0])
    return sorted(ret)


def available(name):
    '''
    Returns ``True`` if the specified service is available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available net-snmp
    '''
    return name in get_all()


def missing(name):
    '''
    The inverse of service.available.
    Returns ``True`` if the specified service is not available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing net-snmp
    '''
    return not name in get_all()


def get_all():
    '''
    Return all installed services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    ret = set()
    cmd = 'svcs -aH -o SVC,STATE -s SVC'
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        ret.add(comps[0])
    return sorted(ret)


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    cmd = '/usr/sbin/svcadm enable -t {0}'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = '/usr/sbin/svcadm disable -t {0}'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    cmd = '/usr/sbin/svcadm restart {0}'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def reload_(name):
    '''
    Reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    cmd = '/usr/sbin/svcadm refresh {0}'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def status(name, sig=None):
    '''
    Return the status for a service, returns a bool whether the service is
    running.

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    '''
    cmd = '/usr/bin/svcs -H -o STATE {0}'.format(name)
    line = __salt__['cmd.run'](cmd)
    if line == 'online':
        return True
    else:
        return False


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    '''
    cmd = '/usr/sbin/svcadm enable {0}'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    cmd = '/usr/sbin/svcadm disable {0}'.format(name)
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
