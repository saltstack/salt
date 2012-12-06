'''
The default service module, if not otherwise specified salt will fall back
to this basic module
'''

# Import Python libs
import os

# Import Salt libs
import salt.utils


grainmap = {
           'Arch': '/etc/rc.d',
           'Debian': '/etc/init.d',
           'Fedora': '/etc/init.d',
           'RedHat': '/etc/init.d',
           'Ubuntu': '/etc/init.d',
           'Gentoo': '/etc/init.d',
           'CentOS': '/etc/init.d',
           'CloudLinux': '/etc/init.d',
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
               'Amazon',
               'Scientific',
               'CloudLinux',
               'Fedora',
               'Gentoo',
               'Ubuntu',
               'Debian',
               'Arch',
              ]
    if __grains__['os'] in disable:
        return False
    # Disable on all non-Linux OSes as well
    if __grains__['kernel'] != 'Linux':
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
    if name == 'salt-minion':
        salt.utils.daemonize_if(__opts__)
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
    return __salt__['status.pid'](sig if sig else name)


def reload(name):
    '''
    Restart the named service

    CLI Example::

        salt '*' service.reload <service name>
    '''
    cmd = os.path.join(grainmap[__grains__['os']],
            name + ' reload')
    return not __salt__['cmd.retcode'](cmd)
