# -*- coding: utf-8 -*-
'''
If Salt's OS detection does not identify a different virtual service module, the minion will fall back to using this basic module, which simply wraps sysvinit scripts.
'''
from __future__ import absolute_import

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
        'ScientificLinux',
        'CloudLinux',
        'Fedora',
        'Gentoo',
        'Ubuntu',
        'Debian',
        'Arch',
        'Arch ARM',
        'ALT',
        'SUSE  Enterprise Server',
        'SUSE',
        'OEL',
        'Linaro',
        'elementary OS',
        'McAfee  OS Server',
        'Mint',
        'Raspbian'
    ))
    if __grains__.get('os', '') in disable:
        return False
    # Disable on all non-Linux OSes as well
    if __grains__['kernel'] != 'Linux':
        return False
    # Suse >=12.0 uses systemd
    if __grains__.get('os_family', '') == 'Suse':
        try:
            # osrelease might be in decimal format (e.g. "12.1"), or for
            # SLES might include service pack (e.g. "11 SP3"), so split on
            # non-digit characters, and the zeroth element is the major
            # number (it'd be so much simpler if it was always "X.Y"...)
            import re
            if int(re.split(r'\D+', __grains__.get('osrelease', ''))[0]) >= 12:
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
        name
    ) + ' start'
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = os.path.join(
        _GRAINMAP.get(__grains__.get('os'), '/etc/init.d'),
        name
    ) + ' stop'
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def restart(name):
    '''
    Restart the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    cmd = os.path.join(
        _GRAINMAP.get(__grains__.get('os'), '/etc/init.d'),
        name
    ) + ' restart'
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


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
    Refreshes config files by calling service reload. Does not perform a full
    restart.

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    cmd = os.path.join(
        _GRAINMAP.get(__grains__.get('os'), '/etc/init.d'),
        name
    ) + ' reload'
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def available(name):
    '''
    Returns ``True`` if the specified service is available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available sshd
    '''
    return name in get_all()


def missing(name):
    '''
    The inverse of service.available.
    Returns ``True`` if the specified service is not available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing sshd
    '''
    return name not in get_all()


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
