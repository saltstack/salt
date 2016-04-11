# -*- coding: utf-8 -*-
'''
The service module for OpenBSD

.. important::
    If you feel that Salt should be using this module to manage services on a
    minion, and it is using a different module (or gives an error similar to
    *'service.start' is not available*), see :ref:`here
    <module-provider-override>`.
'''

# Import python libs
from __future__ import absolute_import
import os
import logging

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import map  # pylint: disable=import-error,redefined-builtin

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)

# XXX enable/disable support would be nice

# Define the module's virtual name
__virtualname__ = 'service'

__func_alias__ = {
    'reload_': 'reload'
}


def __virtual__():
    '''
    Only work on OpenBSD
    '''
    if __grains__['os'] == 'OpenBSD' and os.path.exists('/etc/rc.d/rc.subr'):
        krel = list(list(map(int, __grains__['kernelrelease'].split('.'))))
        # The -f flag, used to force a script to run even if disabled,
        # was added after the 5.0 release.
        # the rcctl(8) command is the preferred way to manage services.
        if krel[0] > 5 or (krel[0] == 5 and krel[1] > 0):
            if not os.path.exists('/usr/sbin/rcctl'):
                return __virtualname__
    return (False, 'The openbsdservice execution module cannot be loaded: '
            'only available on OpenBSD systems.')


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    cmd = '/etc/rc.d/{0} -f start'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = '/etc/rc.d/{0} -f stop'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    cmd = '/etc/rc.d/{0} -f restart'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def status(name, sig=None):
    '''
    Return the status for a service, returns a bool whether the service is
    running.

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    '''
    if sig:
        return bool(__salt__['status.pid'](sig))
    cmd = '/etc/rc.d/{0} -f check'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def reload_(name):
    '''
    .. versionadded:: 2014.7.0

    Reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    cmd = '/etc/rc.d/{0} -f reload'.format(name)
    return not __salt__['cmd.retcode'](cmd)


import re
service_flags_regex = re.compile(r'^\s*(\w[\d\w]*)_flags=(?:(NO)|.*)$')
pkg_scripts_regex = re.compile(r'^\s*pkg_scripts=\'(.*)\'$')
start_daemon_call_regex = re.compile(r'(\s*start_daemon(?!\(\)))')
start_daemon_parameter_regex = re.compile(r'(?:\s+(\w[\w\d]*))')


def _get_rc():
    '''
    Returns a dict where the key is the daemon's name and
    the value a boolean indicating its status (True: enabled or False: disabled).
    Check the daemons started by the system in /etc/rc and
    configured in /etc/rc.conf and /etc/rc.conf.local.
    Also add to the dict all the localy enabled daemons via $pkg_scripts.
    '''
    daemons_flags = {}

    try:
        # now read the system startup script /etc/rc
        # to know what are the system enabled daemons
        with salt.utils.fopen('/etc/rc', 'r') as handle:
            lines = handle.readlines()
    except IOError:
        log.error('Unable to read /etc/rc')
    else:
        for line in lines:
            match = start_daemon_call_regex.match(line)
            if match:
                # the matched line is a call to start_daemon()
                # we remove the function name
                line = line[len(match.group(1)):]
                # we retrieve each daemon name from the parameters of start_daemon()
                for daemon in start_daemon_parameter_regex.findall(line):
                    # mark it as enabled
                    daemons_flags[daemon] = True

    # this will execute rc.conf and rc.conf.local
    # used in /etc/rc at boot to start the daemons
    variables = __salt__['cmd.run']('(. /etc/rc.conf && set)',
                                    clean_env=True,
                                    output_loglevel='quiet',
                                    python_shell=True).split('\n')
    for var in variables:
        match = service_flags_regex.match(var)
        if match:
            # the matched var look like daemon_name_flags=, we test its assigned value
            # NO: disabled, everything else: enabled
            # do not create a new key if the service hasn't been found in /etc/rc, see $pkg_scripts
            if match.group(2) == 'NO':
                daemons_flags[match.group(1)] = False
        else:
            match = pkg_scripts_regex.match(var)
            if match:
                # the matched var is pkg_scripts
                # we can retrieve the name of each localy enabled daemon that wasn't hand started via /etc/rc
                for daemon in match.group(1).split():
                    # create a new key and mark it as enabled
                    daemons_flags[daemon] = True

    return daemons_flags


def available(name):
    '''
    .. versionadded:: 2014.7.0

    Returns ``True`` if the specified service is available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available sshd
    '''
    path = '/etc/rc.d/{0}'.format(name)
    return os.path.isfile(path) and os.access(path, os.X_OK)


def missing(name):
    '''
    .. versionadded:: 2014.7.0

    The inverse of service.available.
    Returns ``True`` if the specified service is not available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing sshd
    '''
    return not available(name)


def get_all():
    '''
    .. versionadded:: 2014.7.0

    Return all available boot services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    services = []
    if not os.path.isdir('/etc/rc.d'):
        return services
    for service in os.listdir('/etc/rc.d'):
        # this will remove rc.subr and all non executable files
        if available(service):
            services.append(service)
    return sorted(services)


def get_enabled():
    '''
    .. versionadded:: 2014.7.0

    Return a list of service that are enabled on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    services = []
    for daemon, is_enabled in six.iteritems(_get_rc()):
        if is_enabled:
            services.append(daemon)
    return sorted(set(get_all()) & set(services))


def enabled(name, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Return True if the named service is enabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    '''
    return name in get_enabled()


def get_disabled():
    '''
    .. versionadded:: 2014.7.0

    Return a set of services that are installed but disabled

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    services = []
    for daemon, is_enabled in six.iteritems(_get_rc()):
        if not is_enabled:
            services.append(daemon)
    return sorted(set(get_all()) & set(services))


def disabled(name):
    '''
    .. versionadded:: 2014.7.0

    Return True if the named service is disabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    '''
    return name in get_disabled()
