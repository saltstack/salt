'''
Service support for Debian systems - uses update-rc.d and service to modify the system
'''

# Import python libs
import glob
import re

# Import salt libs
import salt.utils
from .systemd import _sd_booted


def __virtual__():
    '''
    Only work on Debian and when systemd isn't running
    '''
    if __grains__['os'] == 'Debian' and not _sd_booted():
        return 'service'
    return False


def _get_runlevel():
    '''
    returns the current runlevel
    '''
    return __salt__['cmd.run']('runlevel').split()[1]


def get_enabled():
    '''
    Return a list of service that are enabled on boot

    CLI Example::

        salt '*' service.get_enabled
    '''
    prefix = '/etc/rc{0}.d/S'.format(_get_runlevel())
    ret = set()
    lines = glob.glob('{0}*'.format(prefix))
    for line in lines:
        ret.add(re.split(prefix + '\d+', line)[1])
    return sorted(ret)


def get_disabled():
    '''
    Return a set of services that are installed but disabled

    CLI Example::

        salt '*' service.get_disabled
    '''
    prefix = '/etc/rc{0}.d/K'.format(_get_runlevel())
    ret = set()
    lines = glob.glob('{0}*'.format(prefix))
    for line in lines:
        ret.add(re.split(prefix + '\d+', line)[1])
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
    if name == 'salt-minion':
        salt.utils.daemonize_if(__opts__)
    cmd = 'service {0} restart'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def reload(name):
    '''
    Reload the named service

    CLI Example::

        salt '*' service.reload <service name>
    '''
    cmd = 'service {0} reload'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def force_reload(name):
    '''
    Force-reload the named service

    CLI Example::

        salt '*' service.force_reload <service name>
    '''
    cmd = 'service {0} force-reload'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def status(name, sig=None):
    '''
    Return the status for a service, pass a signature to use to find
    the service via ps

    CLI Example::

        salt '*' service.status <service name>
    '''
    if sig:
        return bool(__salt__['status.pid'](sig))
    cmd = 'service {0} status'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example::

        salt '*' service.enable <service name>
    '''
    cmd = 'update-rc.d {0} enable'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example::

        salt '*' service.disable <service name>
    '''
    cmd = 'update-rc.d {0} disable'.format(name)
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
