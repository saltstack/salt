'''
The default service module, if not otherwise specified salt will fall back
to this basic module
'''

import os

grainmap = {
           'Arch': '/etc/rc.d',
           'Debian': '/etc/init.d',
           'Fedora': '/etc/init.d',
           'RedHat': '/etc/init.d',
           'Ubuntu': '/etc/init.d',
           'Gentoo': '/etc/init.d',
           'CentOS': '/etc/init.d',
           'Amazon': '/etc/init.d',
           'SunOS': '/etc/init.d',
          }

def __virtual__():
    '''
    Only work on systems which default to systemd
    '''
    # Disable on these platforms, specific service modules exist:
    disable = [
               'RedHat',
               'CentOS',
               'Scientific',
               'Fedora',
               'Gentoo',
               'Ubuntu',
               'FreeBSD',
               'Windows',
              ]
    if __grains__['os'] in disable:
        return False
    return 'service'


def start(name):
    '''
    Start the specified service

    CLI Example::

        salt '*' service.start <service name>
    '''
    cmd = os.path.join(grainmap[__grains__['os']],
            name + ' start')
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example::

        salt '*' service.stop <service name>
    '''
    cmd = os.path.join(grainmap[__grains__['os']],
            name + ' stop')
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example::

        salt '*' service.restart <service name>
    '''
    cmd = os.path.join(grainmap[__grains__['os']],
            name + ' restart')
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


def reload(name):
    '''
    Restart the named service

    CLI Example::

        salt '*' service.reload <service name>
    '''
    cmd = os.path.join(grainmap[__grains__['os']],
            name + ' reload')
    return not __salt__['cmd.retcode'](cmd)
