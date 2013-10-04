# -*- coding: utf-8 -*-
'''
Service support for Debian systems (uses update-rc.d and /sbin/service)
'''

# Import python libs
import glob
import re

# Import salt libs
from .systemd import _sd_booted

__func_alias__ = {
    'reload_': 'reload'
}


def __virtual__():
    '''
    Only work on Debian and when systemd isn't running
    '''
    if __grains__['os'] in ('Debian', 'Raspbian') and not _sd_booted():
        return 'service'
    return False


def _get_runlevel():
    '''
    returns the current runlevel
    '''
    out = __salt__['cmd.run']('runlevel')
    # unknown can be returned while inside a container environment, since
    # this is due to a lack of init, it should be safe to assume runlevel
    # 2, which is Debian's default. If not, all service related states
    # will throw an out of range exception here which will cause
    # other functions to fail.
    if 'unknown' in out:
        return '2'
    else:
        return out.split()[1]


def get_enabled():
    '''
    Return a list of service that are enabled on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    prefix = '/etc/rc[S{0}].d/S'.format(_get_runlevel())
    ret = set()
    lines = glob.glob('{0}*'.format(prefix))
    for line in lines:
        ret.add(re.split(prefix + r'\d+', line)[1])
    return sorted(ret)


def get_disabled():
    '''
    Return a set of services that are installed but disabled

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    return sorted(set(get_all()) - set(get_enabled()))


def available(name):
    '''
    Returns ``True`` if the specified service is available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available sshd
    '''
    return name in get_all()


def get_all():
    '''
    Return all available boot services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    ret = set()
    lines = glob.glob('/etc/init.d/*')
    for line in lines:
        service = line.split('/etc/init.d/')[1]
        # Remove README.  If it's an enabled service, it will be added back in.
        if service != 'README':
            ret.add(service)
    return sorted(ret | set(get_enabled()))


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    cmd = 'service {0} start'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = 'service {0} stop'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    cmd = 'service {0} restart'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def reload_(name):
    '''
    Reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    cmd = 'service {0} reload'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def force_reload(name):
    '''
    Force-reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.force_reload <service name>
    '''
    cmd = 'service {0} force-reload'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def status(name, sig=None):
    '''
    Return the status for a service, pass a signature to use to find
    the service via ps

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    '''
    if sig:
        return bool(__salt__['status.pid'](sig))
    cmd = 'service {0} status'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    '''
    cmd = 'update-rc.d {0} enable'.format(name)
    osmajor = __grains__['osrelease'].split('.')[0]
    if int(osmajor) >= 6:
        cmd = 'insserv {0} && '.format(name) + cmd
    return not __salt__['cmd.retcode'](cmd)


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    cmd = 'update-rc.d {0} disable'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def enabled(name):
    '''
    Return True if the named service is enabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    '''
    return name in get_enabled()


def disabled(name):
    '''
    Return True if the named service is enabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    '''
    return name in get_disabled()
