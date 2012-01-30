'''
Top level package command wrapper, used to translate the os detected by the
grains to the correct service manager
'''

import os


def __virtual__():
    '''
    Only work on systems which default to systemd
    '''
    # Disable on these platforms, specific service modules exist:
    enable = [
               'RedHat',
               'CentOS',
               'Fedora',
              ]
    if __grains__['os'] in enable:
        if __grains__['os'] == 'Fedora':
            if __grains__['osrelease'] > 15:
                return False
        return 'service'
    return False

def _runlevel():
    '''
    Return the current runlevel
    '''
    out = __salt__['cmd.run']('runlevel').strip()
    return out.split()[1]


def get_enabled():
    '''
    Return the enabled services

    CLI Example::

        salt '*' service.get_enabled
    '''
    rlevel = _runlevel()
    ret = set()
    cmd = 'chkconfig --list'
    lines = __salt__['cmd.run'](cmd).split('\n')
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        if '{0}:on'.format(rlevel) in line:
            ret.add(comps[0])
    return sorted(ret)

def get_disabled():
    '''
    Return the disabled services

    CLI Example::

        salt '*' service.get_enabled
    '''
    rlevel = _runlevel()
    ret = set()
    cmd = 'chkconfig --list'
    lines = __salt__['cmd.run'](cmd).split('\n')
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        if not '{0}:on'.format(rlevel) in line:
            ret.add(comps[0])
    return sorted(ret)

def get_all():
    '''
    Return all installed services

    CLI Example::

        salt '*' service.get_enabled
    '''
    return sorted(get_enabled() + get_disabled())

def start(name):
    '''
    Start the specified service

    CLI Example::

        salt '*' service.start <service name>
    '''
    cmd = 'service {0} start'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example::

        salt '*' service.stop <service name>
    '''
    cmd = 'service {0} stop'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example::

        salt '*' service.restart <service name>
    '''
    cmd = 'service {0} restart'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def status(name, sig=None):
    '''
    Return the status for a service, returns the PID or an empty string if the
    service is running or not, pass a signature to use to find the service via
    ps

    CLI Example::

        salt '*' service.status <service name> [service signature]
    '''
    cmd = 'service {0} status'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def enable(name):
    '''
    Enable the named service to start at boot

    CLI Example::

        salt '*' service.enable <service name>
    '''
    cmd = 'chkconfig {0} on'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def disable(name):
    '''
    Disable the named service to start at boot

    CLI Example::

        salt '*' service.disable <service name>
    '''
    cmd = 'chkconfig {0} off'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def enabled(name):
    '''
    Check to see if the named service is enabled to start on boot

    CLI Example::

        salt '*' service.enabled <service name>
    '''
    if name in get_enabled():
        return True
    return False


def disabled(name):
    '''
    Check to see if the named service is disabled to start on boot

    CLI Example::

        salt '*' service.disabled <service name>
    '''
    if name in get_disabled():
        return True
    return False
