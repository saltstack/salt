# -*- coding: utf-8 -*-
'''
daemontools service module. This module will create daemontools type
service watcher.

This module is compatible with the :mod:`service <salt.states.service>` states,
so it can be used to maintain services using the ``provider`` argument:

.. code-block:: yaml

    myservice:
      service.running:
        - provider: daemontools
'''
from __future__ import absolute_import

# Import python libs
import logging
import os
import os.path
import re

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

# Function alias to not shadow built-ins.
__func_alias__ = {
    'reload_': 'reload'
}

log = logging.getLogger(__name__)

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


def __virtual__():
    # Ensure that daemontools is installed properly.
    BINS = frozenset(('svc', 'supervise', 'svok'))
    return all(salt.utils.which(b) for b in BINS)


def _service_path(name):
    '''
    build service path
    '''
    if not SERVICE_DIR:
        raise CommandExecutionError("Could not find service directory.")
    return '{0}/{1}'.format(SERVICE_DIR, name)


#-- states.service  compatible args
def start(name):
    '''
    Starts service via daemontools

    CLI Example:

    .. code-block:: bash

        salt '*' daemontools.start <service name>
    '''
    __salt__['file.remove']('{0}/down'.format(_service_path(name)))
    cmd = 'svc -u {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


#-- states.service compatible args
def stop(name):
    '''
    Stops service via daemontools

    CLI Example:

    .. code-block:: bash

        salt '*' daemontools.stop <service name>
    '''
    __salt__['file.touch']('{0}/down'.format(_service_path(name)))
    cmd = 'svc -d {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def term(name):
    '''
    Send a TERM to service via daemontools

    CLI Example:

    .. code-block:: bash

        salt '*' daemontools.term <service name>
    '''
    cmd = 'svc -t {0}'.format(_service_path(name))
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


#-- states.service compatible
def reload_(name):
    '''
    Wrapper for term()

    CLI Example:

    .. code-block:: bash

        salt '*' daemontools.reload <service name>
    '''
    term(name)


#-- states.service compatible
def restart(name):
    '''
    Restart service via daemontools. This will stop/start service

    CLI Example:

    .. code-block:: bash

        salt '*' daemontools.restart <service name>
    '''
    ret = 'restart False'
    if stop(name) and start(name):
        ret = 'restart True'
    return ret


#-- states.service compatible
def full_restart(name):
    '''
    Calls daemontools.restart() function

    CLI Example:

    .. code-block:: bash

        salt '*' daemontools.full_restart <service name>
    '''
    restart(name)


#-- states.service compatible
def status(name, sig=None):
    '''
    Return the status for a service via daemontools, return pid if running

    CLI Example:

    .. code-block:: bash

        salt '*' daemontools.status <service name>
    '''
    cmd = 'svstat {0}'.format(_service_path(name))
    out = __salt__['cmd.run_stdout'](cmd, python_shell=False)
    try:
        pid = re.search(r'\(pid (\d+)\)', out).group(1)
    except AttributeError:
        pid = ''
    return pid


def available(name):
    '''
    Returns ``True`` if the specified service is available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' daemontools.available foo
    '''
    return name in get_all()


def missing(name):
    '''
    The inverse of daemontools.available.
    Returns ``True`` if the specified service is not available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' daemontools.missing foo
    '''
    return name not in get_all()


def get_all():
    '''
    Return a list of all available services

    CLI Example:

    .. code-block:: bash

        salt '*' daemontools.get_all
    '''
    if not SERVICE_DIR:
        raise CommandExecutionError("Could not find service directory.")
    #- List all daemontools services in
    return sorted(os.listdir(SERVICE_DIR))


def enabled(name, **kwargs):
    '''
    Return True if the named service is enabled, false otherwise
    A service is considered enabled if in your service directory:
    - an executable ./run file exist
    - a file named "down" does not exist

    .. versionadded:: 2015.5.7

    name
        Service name

    CLI Example:

    .. code-block:: bash

        salt '*' daemontools.enabled <service name>
    '''
    if not available(name):
        log.error('Service {0} not found'.format(name))
        return False

    run_file = os.path.join(SERVICE_DIR, name, 'run')
    down_file = os.path.join(SERVICE_DIR, name, 'down')

    return (
        os.path.isfile(run_file) and
        os.access(run_file, os.X_OK) and not
        os.path.isfile(down_file)
    )


def disabled(name):
    '''
    Return True if the named service is enabled, false otherwise

    .. versionadded:: 2015.5.6

    CLI Example:

    .. code-block:: bash

        salt '*' daemontools.disabled <service name>
    '''
    return not enabled(name)
