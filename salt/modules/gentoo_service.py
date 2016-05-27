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

from __future__ import absolute_import

# Import Python libs
import logging

# Import salt libs
import salt.utils.systemd
import salt.utils.odict as odict

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'service'


def __virtual__():
    '''
    Only work on systems which default to OpenRC
    '''
    if __grains__['os'] == 'Gentoo' and not salt.utils.systemd.booted(__context__):
        return __virtualname__
    return (False, 'The gentoo_service execution module cannot be loaded: '
            'only available on Gentoo/Open-RC systems.')


def _ret_code(cmd):
    log.debug('executing [{0}]'.format(cmd))
    sts = __salt__['cmd.retcode'](cmd, python_shell=False)
    return sts


def _list_services():
    return __salt__['cmd.run']('rc-update -v show').splitlines()


def _get_service_list(include_enabled=True, include_disabled=False):
    enabled_services = dict()
    disabled_services = set()
    lines = _list_services()
    for line in lines:
        if '|' not in line:
            continue
        service = [l.strip() for l in line.split('|')]
        # enabled service should have runlevels
        if service[1]:
            if include_enabled:
                enabled_services.update({service[0]: sorted(service[1].split())})
            continue
        # in any other case service is disabled
        if include_disabled:
            disabled_services.update({service[0]: []})
    return enabled_services, disabled_services


def _enable_delta(name, requested_runlevels):
    all_enabled = get_enabled()
    current_levels = set(all_enabled[name] if name in all_enabled else [])
    enabled_levels = requested_runlevels - current_levels
    disabled_levels = current_levels - requested_runlevels
    return enabled_levels, disabled_levels


def _disable_delta(name, requested_runlevels):
    all_enabled = get_enabled()
    current_levels = set(all_enabled[name] if name in all_enabled else [])
    return current_levels & requested_runlevels


def _service_cmd(*args):
    return '/etc/init.d/{0} {1}'.format(args[0], ' '.join(args[1:]))


def _enable_disable_cmd(name, command, runlevels=()):
    return 'rc-update {0} {1} {2}'.format(command, name, ' '.join(sorted(runlevels))).strip()


def get_enabled():
    '''
    Return a list of service that are enabled on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    (enabled_services, disabled_services) = _get_service_list()
    return odict.OrderedDict(enabled_services)


def get_disabled():
    '''
    Return a set of services that are installed but disabled

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    (enabled_services, disabled_services) = _get_service_list(include_enabled=False,
                                                              include_disabled=True)
    return sorted(disabled_services)


def available(name):
    '''
    Returns ``True`` if the specified service is available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available sshd
    '''
    (enabled_services, disabled_services) = _get_service_list(include_enabled=True,
                                                              include_disabled=True)
    return name in enabled_services or name in disabled_services


def missing(name):
    '''
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
    Return all available boot services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    (enabled_services, disabled_services) = _get_service_list(include_enabled=True,
                                                              include_disabled=True)
    enabled_services.update(dict([(s, []) for s in disabled_services]))
    return odict.OrderedDict(enabled_services)


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    cmd = _service_cmd(name, 'start')
    return not _ret_code(cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = _service_cmd(name, 'stop')
    return not _ret_code(cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    cmd = _service_cmd(name, 'restart')
    return not _ret_code(cmd)


def reload_(name):
    '''
    Reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    cmd = _service_cmd(name, 'reload')
    return not _ret_code(cmd)


def zap(name):
    '''
    Resets service state

    CLI Example:

    .. code-block:: bash

        salt '*' service.zap <service name>
    '''
    cmd = _service_cmd(name, 'zap')
    return not _ret_code(cmd)


def status(name, sig=None):
    '''
    Return the status for a service, returns the PID or an empty string if the
    service is running or not, pass a signature to use to find the service via
    ps

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name> [service signature]
    '''
    if sig:
        return bool(__salt__['status.pid'](sig))
    cmd = _service_cmd(name, 'status')
    return not _ret_code(cmd)


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name> <runlevels=single-runlevel>
        salt '*' service.enable <service name> <runlevels=[runlevel1,runlevel2]>
    '''
    if 'runlevels' in kwargs:
        requested_levels = set(kwargs['runlevels'] if isinstance(kwargs['runlevels'],
                                                                 list) else [kwargs['runlevels']])
        enabled_levels, disabled_levels = _enable_delta(name, requested_levels)
        commands = []
        if disabled_levels:
            commands.append(_enable_disable_cmd(name, 'delete', disabled_levels))
        if enabled_levels:
            commands.append(_enable_disable_cmd(name, 'add', enabled_levels))
        if not commands:
            return True
    else:
        commands = [_enable_disable_cmd(name, 'add')]
    for cmd in commands:
        if _ret_code(cmd):
            return False
    return True


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name> <runlevels=single-runlevel>
        salt '*' service.disable <service name> <runlevels=[runlevel1,runlevel2]>
    '''
    levels = []
    if 'runlevels' in kwargs:
        requested_levels = set(kwargs['runlevels'] if isinstance(kwargs['runlevels'],
                                                                 list) else [kwargs['runlevels']])
        levels = _disable_delta(name, requested_levels)
        if not levels:
            return True
    cmd = _enable_disable_cmd(name, 'delete', levels)
    return not _ret_code(cmd)


def enabled(name, **kwargs):
    '''
    Return True if the named service is enabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name> <runlevels=single-runlevel>
        salt '*' service.enabled <service name> <runlevels=[runlevel1,runlevel2]>
    '''
    enabled_services = get_enabled()
    if name not in enabled_services:
        return False
    if 'runlevels' not in kwargs:
        return True
    requested_levels = set(kwargs['runlevels'] if isinstance(kwargs['runlevels'],
                                                             list) else [kwargs['runlevels']])
    return len(requested_levels - set(enabled_services[name])) == 0


def disabled(name):
    '''
    Return True if the named service is enabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name> <runlevels=[runlevel]>
    '''
    return name in get_disabled()
