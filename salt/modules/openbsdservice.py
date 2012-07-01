'''
The service module for OpenBSD
'''

import os


# XXX enable/disable support would be nice


def __virtual__():
    '''
    Only work on OpenBSD
    '''
    if __grains__['os'] == 'OpenBSD' and os.path.exists('/etc/rc.d/rc.subr'):
        return 'service'
    return False


def start(name):
    '''
    Start the specified service

    CLI Example::

        salt '*' service.start <service name>
    '''
    cmd = '/etc/rc.d/{0} -f start'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example::

        salt '*' service.stop <service name>
    '''
    cmd = '/etc/rc.d/{0} -f stop'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example::

        salt '*' service.restart <service name>
    '''
    cmd = '/etc/rc.d/{0} -f restart'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def status(name):
    '''
    Return the status for a service, returns a bool whether the service is
    running.

    CLI Example::

        salt '*' service.status <service name>
    '''
    cmd = '/etc/rc.d/{0} -f check'.format(name)
    return not __salt__['cmd.retcode'](cmd)
