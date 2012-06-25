'''
Top level package command wrapper, used to translate the os detected by the
grains to the correct service manager
'''


def __virtual__():
    '''
    Only work on systems which default to systemd
    '''
    if __grains__['os'] == 'Gentoo':
        return 'service'
    return False


def get_enabled():
    '''
    Return a list of service that are enabled on boot

    CLI Example::

        salt '*' service.get_enabled
    '''
    ret = set()
    lines = __salt__['cmd.run']('rc-update show').strip().split('\n')
    for line in lines:
        if not '|' in line:
            continue
        if 'shutdown' in line:
            continue
        ret.add(line.split('|')[0].strip())
    return sorted(ret)


def get_disabled():
    '''
    Return a set of services that are installed but disabled

    CLI Example::

        salt '*' service.get_disabled
    '''
    ret = set()
    lines = __salt__['cmd.run']('rc-update -v show').strip().split('\n')
    for line in lines:
        if not '|' in line:
            continue
        elif 'shutdown' in line:
            continue
        comps = line.split()
        if len(comps) < 3:
            ret.add(comps[0])
    return sorted(ret)

def get_all():
    '''
    Return all available boot services

    CLI Example::

        salt '*' service.get_all
    '''
    return sorted(get_enabled() + get_disabled())


def start(name):
    '''
    Start the specified service

    CLI Example::

        salt '*' service.start <service name>
    '''
    cmd = '/etc/init.d/{0} start'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example::

        salt '*' service.stop <service name>
    '''
    cmd = '/etc/init.d/{0} stop'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example::

        salt '*' service.restart <service name>
    '''
    cmd = '/etc/init.d/{0} restart'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def status(name, sig=None):
    '''
    Return the status for a service, returns the PID or an empty string if the
    service is running or not, pass a signature to use to find the service via
    ps

    CLI Example::

        salt '*' service.status <service name> [service signature]
    '''
    sig = name if not sig else sig
    cmd = "{0[ps]} | grep {1} | grep -v grep | awk '{{print $2}}'".format(
            __grains__, sig)
    return __salt__['cmd.run'](cmd).strip()

def enable(name):
    '''
    Enable the named service to start at boot

    CLI Example::

        salt '*' service.enable <service name>
    '''
    cmd = 'rc-update add {0} default'.format(name)
    return not __salt__['cmd.retcode'](cmd)

def disable(name):
    '''
    Disable the named service to start at boot

    CLI Example::

        salt '*' service.disable <service name>
    '''
    cmd = 'rc-update delete {0} default'.format(name)
    return not __salt__['cmd.retcode'](cmd)

def enabled(name):
    '''
    Return True if the named servioce is enabled, false otherwise

    CLI Example::

        salt '*' service.enabled <service name>
    '''
    return name in get_enabled()

def disabled(name):
    '''
    Return True if the named servioce is enabled, false otherwise

    CLI Example::

        salt '*' service.disabled <service name>
    '''
    return name in get_disabled()
