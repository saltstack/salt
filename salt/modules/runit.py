# -*- coding: utf-8 -*-
'''
runit service module

This module is compatible with the :mod:`service <salt.states.service>` states,
so it can be used to maintain services using the ``provider`` argument:

.. code-block:: yaml

    myservice:
      service:
        - running
        - provider: runit

Note that the ``enabled`` argument is not available with this provider.
'''
from __future__ import absolute_import

# Import python libs
import os
import re

# Import salt libs
from salt.exceptions import CommandExecutionError

__func_alias__ = {
    'reload_': 'reload'
}

VALID_SERVICE_DIRS = [
    '/service',
    '/var/service',
    '/etc/service',
]
SERVICE_DIR = None
for service_dir in VALID_SERVICE_DIRS:
    if os.path.exists(service_dir):
        SERVICE_DIR = service_dir
        break


def _service_path(name):
    '''
    build service path
    '''
    if not SERVICE_DIR:
        raise CommandExecutionError("Could not find service directory.")
    return '{0}/{1}'.format(SERVICE_DIR, name)


def start(name):
    '''
    Starts service via runit

    CLI Example:

    .. code-block:: bash

        salt '*' runit.start <service name>
    '''
    cmd = 'sv start {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stops service via runit

    CLI Example:

    .. code-block:: bash

        salt '*' runit.stop <service name>
    '''
    cmd = 'sv stop {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd)


def term(name):
    '''
    Send a TERM to service via runit

    CLI Example:

    .. code-block:: bash

        salt '*' runit.term <service name>
    '''
    cmd = 'sv term {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd)


def reload_(name):
    '''
    Send a HUP to service via runit

    CLI Example:

    .. code-block:: bash

        salt '*' runit.reload <service name>
    '''
    cmd = 'sv reload {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart service via runit. This will stop/start service

    CLI Example:

    .. code-block:: bash

        salt '*' runit.restart <service name>
    '''
    cmd = 'sv restart {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd)


def full_restart(name):
    '''
    Calls runit.restart() function

    CLI Example:

    .. code-block:: bash

        salt '*' runit.full_restart <service name>
    '''
    restart(name)


def status(name, sig=None):
    '''
    Return the status for a service via runit, return pid if running

    CLI Example:

    .. code-block:: bash

        salt '*' runit.status <service name>
    '''
    cmd = 'sv status {0}'.format(_service_path(name))
    out = __salt__['cmd.run_stdout'](cmd)
    try:
        pid = re.search(r'{0}: \(pid (\d+)\)'.format(name), out).group(1)
    except AttributeError:
        pid = ''
    return pid


def available(name):
    '''
    Returns ``True`` if the specified service is available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' runit.available foo
    '''
    return name in get_all()


def missing(name):
    '''
    The inverse of runit.available.
    Returns ``True`` if the specified service is not available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' runit.missing foo
    '''
    return name not in get_all()


def get_all():
    '''
    Return a list of all available services

    CLI Example:

    .. code-block:: bash

        salt '*' runit.get_all
    '''
    if not SERVICE_DIR:
        raise CommandExecutionError("Could not find service directory.")
    return sorted(os.listdir(SERVICE_DIR))
