'''
The default service module, if not otherwise specified salt will fall back
to this basic module
'''

# Import python libs
import os

# Import salt libs
import salt.utils
from salt.exceptions import CommandNotFoundError, CommandExecutionError


@salt.utils.memoize
def _init(osname, service=None):
    """
    The default is almost always /etc/init.d for services.
    Only specify paths that are not the default such as Arch.
    """
    path_map = {
        'Arch': '/etc/rc.d',
    }
    default = '/etc/init.d'
    if service:
        ret = os.path.join(path_map.get(osname, default), service)
    else:
        ret = path_map.get(osname, default)

    if service and not os.path.exists(ret):
        msg = 'Init script for {0} not found!'
        raise CommandNotFoundError(msg.format(service))
    elif not service and not os.path.exists(default):
        msg = 'Directory {0} not found!'
        raise CommandExecutionError(msg.format(default))
    return ret

def __virtual__():
    '''
    Only work on systems which default to systemd
    '''
    # Disable on these platforms, specific service modules exist:
    disable = [
        'ALT',
        'Amazon',
        'Arch',
        'CentOS',
        'CloudLinux',
        'Debian',
        'Fedora',
        'Gentoo',
        'OEL',
        'RedHat',
        'Scientific',
        'Ubuntu',
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
    cmd = '{0} start'.format(_init(__grains__['os'], name))
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example::

        salt '*' service.stop <service name>
    '''
    cmd = '{0} stop'.format(_init(__grains__['os'], name))
    return not __salt__['cmd.retcode'](cmd)


def restart(name, **kwargs):
    '''
    Restart the specified service

    CLI Example::

        salt '*' service.restart <service name>
    '''
    cmd = '{0} restart'.format(_init(__grains__['os'], name))
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
    Restart the specified service

    CLI Example::

        salt '*' service.reload <service name>
    '''
    cmd = '{0} reload'.format(_init(__grains__['os'], name))
    return not __salt__['cmd.retcode'](cmd)


def get_all():
    '''
    Return a list of all available services

    CLI Example::

        salt '*' service.get_al
    '''
    if not os.path.isdir(GRAINMAP[__grains__['os']]):
        return []
    return sorted(os.listdir(GRAINMAP[__grains__['os']]))


def available(name):
    '''
    Return if the specified service is available

    CLI Example::

        salt '*' service.available
    '''
    return name in get_all()
