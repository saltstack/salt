# -*- coding: utf-8 -*-
'''
Top level package command wrapper, used to translate the os detected by grains
to the correct service manager

.. important::
    If you feel that Salt should be using this module to manage services on a
    minion, and it is using a different module (or gives an error similar to
    *'service.start' is not available*), see :ref:`here
    <module-provider-override>`.
'''

# Import Python libs
from __future__ import absolute_import

# Define the module's virtual name
__virtualname__ = 'service'


def __virtual__():
    '''
    Only work on systems which default to systemd
    '''
    if __grains__['os'] == 'Gentoo':
        return __virtualname__
    return False


def get_enabled():
    '''
    Return a list of service that are enabled on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    ret = set()
    lines = __salt__['cmd.run']('rc-update show').splitlines()
    for line in lines:
        if '|' not in line:
            continue
        if 'shutdown' in line:
            continue
        ret.add(line.split('|')[0].strip())
    return sorted(ret)


def get_disabled():
    '''
    Return a set of services that are installed but disabled

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    ret = set()
    lines = __salt__['cmd.run']('rc-update -v show').splitlines()
    for line in lines:
        if '|' not in line:
            continue
        elif 'shutdown' in line:
            continue
        comps = line.split()
        if len(comps) < 3:
            ret.add(comps[0])
    return sorted(ret)


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
    Return all available boot services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    return sorted(get_enabled() + get_disabled())


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    cmd = '/etc/init.d/{0} start'.format(name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = '/etc/init.d/{0} stop'.format(name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    cmd = '/etc/init.d/{0} restart'.format(name)
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


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    '''
    cmd = 'rc-update add {0} default'.format(name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    cmd = 'rc-update delete {0} default'.format(name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def enabled(name, **kwargs):
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
