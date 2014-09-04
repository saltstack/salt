# -*- coding: utf-8 -*-
'''
The rcctl service module for OpenBSD
'''

# Import python libs
import os
import re

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.exceptions import CommandNotFoundError

__func_alias__ = {
    'reload_': 'reload'
}

# Define the module's virtual name
__virtualname__ = 'service'


def __virtual__():
    '''
    rcctl(8) is only available on OpenBSD.
    '''
    if __grains__['os'] == 'OpenBSD' and os.path.exists('/usr/sbin/rcctl'):
        return __virtualname__
    return False


@decorators.memoize
def _cmd():
    '''
    Return the full path to the rcctl(8) command.
    '''
    rcctl = salt.utils.which('rcctl')
    if not rcctl:
        raise CommandNotFoundError
    return rcctl


def _get_flags(**kwargs):
    '''
    Return the configured service flags.
    '''
    flags = kwargs.get('flags', \
                       __salt__['config.option']('service.flags', \
                       default=''))
    return flags


def available(name):
    '''
    Return True if the named service is available.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available sshd
    '''
    cmd = '{0} status {1}'.format(_cmd(), name)
    if __salt__['cmd.retcode'](cmd) == 2:
        return False
    return True


def missing(name):
    '''
    The inverse of service.available.
    Return True if the named service is not available.

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing sshd
    '''
    return not available(name)


def get_all():
    '''
    Return all installed services.

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    ret = []
    service = _cmd()
    for svc in __salt__['cmd.run']('{0} status'.format(service)).splitlines():
        svc = re.sub('(_flags|)=.*$', '', svc)
        ret.append(svc)
    return sorted(ret)


def get_disabled():
    '''
    Return what services are available but not enabled to start at boot.

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    ret = []
    service = _cmd()
    for svc in __salt__['cmd.run']('{0} status'.format(service)).splitlines():
        if svc.endswith("=NO"):
            svc = re.sub('(_flags|)=.*$', '', svc)
            ret.append(svc)
    return sorted(ret)


def get_enabled():
    '''
    Return what services are set to run on boot.

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    ret = []
    service = _cmd()
    for svc in __salt__['cmd.run']('{0} status'.format(service)).splitlines():
        if not svc.endswith("=NO"):
            svc = re.sub('(_flags|)=.*$', '', svc)
            ret.append(svc)
    return sorted(ret)


def start(name):
    '''
    Start the named service.

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    cmd = '{0} -f start {1}'.format(_cmd(), name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the named service.

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = '{0} stop {1}'.format(_cmd(), name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service.

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    cmd = '{0} -f restart {1}'.format(_cmd(), name)
    return not __salt__['cmd.retcode'](cmd)


def reload_(name):
    '''
    Reload the named service.

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    cmd = '{0} reload {1}'.format(_cmd(), name)
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

    cmd = '{0} check {1}'.format(_cmd(), name)
    return not __salt__['cmd.retcode'](cmd)


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot.

    flags : None
        Set optional flags to run the service with.

    service.flags can be used to change the default flags.

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
        salt '*' service.enable <service name> flags=<flags>
    '''
    flags = _get_flags(**kwargs)
    cmd = '{0} enable {1} flags {2}'.format(_cmd(), name, flags)
    return not __salt__['cmd.retcode'](cmd)


def disable(name, **kwargs):
    '''
    Disable the named service to not start at boot.

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    cmd = '{0} disable {1}'.format(_cmd(), name)
    return not __salt__['cmd.retcode'](cmd)


def disabled(name):
    '''
    Return True if the named service is disabled at boot, False otherwise.

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    '''
    cmd = '{0} status {1}'.format(_cmd(), name)
    return not __salt__['cmd.retcode'](cmd) == 0


def enabled(name, **kwargs):
    '''
    Return True if the named service is enabled at boot and the provided
    flags match the configured ones (if any). Return False otherwise.

    name
        Service name

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
        salt '*' service.enabled <service name> flags=<flags>
    '''
    cmd = '{0} status {1}'.format(_cmd(), name)
    if not __salt__['cmd.retcode'](cmd):
        # also consider a service disabled if the current flags are different
        # than the configured ones so we have a chance to update them
        flags = _get_flags(**kwargs)
        cur_flags = __salt__['cmd.run_stdout']('{0} status {1}'.format(_cmd(), name))
        if format(flags) == format(cur_flags):
            return True

    return False
