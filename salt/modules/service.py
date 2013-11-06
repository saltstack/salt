# -*- coding: utf-8 -*-
'''
The default service module, if not otherwise specified salt will fall back
to this basic module
'''

# Import python libs
import os

__func_alias__ = {
    'reload_': 'reload'
}

_GRAINMAP = {
    'Arch': '/etc/rc.d',
    'Arch ARM': '/etc/rc.d'
}


def __virtual__():
    '''
    Only work on systems which exclusively use sysvinit
    '''
    # Disable on these platforms, specific service modules exist:
    disable = set((
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
        'Arch ARM',
        'ALT',
        'SUSE  Enterprise Server',
        'OEL',
        'Linaro',
        'elementary OS',
        'McAfee  OS Server'
    ))
    if __grains__.get('os', '') in disable:
        return False
    # Disable on all non-Linux OSes as well
    if __grains__['kernel'] != 'Linux':
        return False
    # Suse >=12.0 uses systemd
    if __grains__.get('os', '') == 'openSUSE':
        try:
            if int(__grains__.get('osrelease', '').split('.')[0]) >= 12:
                return False
        except ValueError:
            return False
    return 'service'


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    cmd = os.path.join(
        _GRAINMAP.get(__grains__.get('os'), '/etc/init.d'),
        name + ' start'
    )
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = os.path.join(
        _GRAINMAP.get(__grains__.get('os'), '/etc/init.d'),
        name + ' stop'
    )
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    cmd = os.path.join(
        _GRAINMAP.get(__grains__.get('os'), '/etc/init.d'),
        name + ' restart'
    )
    return not __salt__['cmd.retcode'](cmd)


def status(name, sig=None):
    '''
    Return the status for a service, returns the PID or an empty string if the
    service is running or not, pass a signature to use to find the service via
    ps

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name> [service signature]
    '''
    return __salt__['status.pid'](sig if sig else name)


def reload_(name):
    '''
    Restart the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    cmd = os.path.join(
        _GRAINMAP.get(__grains__.get('os'), '/etc/init.d'),
        name + ' reload'
    )
    return not __salt__['cmd.retcode'](cmd)


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
    Return a list of all available services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    if not os.path.isdir(_GRAINMAP.get(__grains__.get('os'), '/etc/init.d')):
        return []
    return sorted(os.listdir(_GRAINMAP.get(__grains__.get('os'), '/etc/init.d')))
