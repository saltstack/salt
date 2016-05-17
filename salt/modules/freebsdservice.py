# -*- coding: utf-8 -*-
'''
The service module for FreeBSD

.. important::
    If you feel that Salt should be using this module to manage services on a
    minion, and it is using a different module (or gives an error similar to
    *'service.start' is not available*), see :ref:`here
    <module-provider-override>`.
'''
from __future__ import absolute_import

# Import python libs
import logging
import os

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.exceptions import CommandNotFoundError

__func_alias__ = {
    'reload_': 'reload'
}

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'service'


def __virtual__():
    '''
    Only work on FreeBSD
    '''
    # Disable on these platforms, specific service modules exist:
    if __grains__['os'] == 'FreeBSD':
        return __virtualname__
    return False


@decorators.memoize
def _cmd():
    '''
    Return full path to service command
    '''
    service = salt.utils.which('service')
    if not service:
        raise CommandNotFoundError('\'service\' command not found')
    return service


def _get_rcscript(name):
    '''
    Return full path to service rc script
    '''
    cmd = '{0} -r'.format(_cmd())
    for line in __salt__['cmd.run_stdout'](cmd, python_shell=False).splitlines():
        if line.endswith('{0}{1}'.format(os.path.sep, name)):
            return line
    return None


def _get_rcvar(name):
    '''
    Return rcvar
    '''
    if not available(name):
        log.error('Service {0} not found'.format(name))
        return False

    cmd = '{0} {1} rcvar'.format(_cmd(), name)

    for line in __salt__['cmd.run_stdout'](cmd, python_shell=False).splitlines():
        if '_enable="' not in line:
            continue
        rcvar, _ = line.split('=', 1)
        return rcvar

    return None


def get_enabled():
    '''
    Return what services are set to run on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    ret = []
    service = _cmd()
    for svc in __salt__['cmd.run']('{0} -e'.format(service)).splitlines():
        ret.append(os.path.basename(svc))

    # This is workaround for bin/173454 bug
    for svc in get_all():
        if svc in ret:
            continue
        if not os.path.exists('/etc/rc.conf.d/{0}'.format(svc)):
            continue
        if enabled(svc):
            ret.append(svc)

    return sorted(ret)


def get_disabled():
    '''
    Return what services are available but not enabled to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    en_ = get_enabled()
    all_ = get_all()
    return sorted(set(all_) - set(en_))


def _switch(name,                   # pylint: disable=C0103
            on,                     # pylint: disable=C0103
            **kwargs):
    '''
    Switch on/off service start at boot.
    '''
    if not available(name):
        return False

    rcvar = _get_rcvar(name)
    if not rcvar:
        log.error('rcvar for service {0} not found'.format(name))
        return False

    config = kwargs.get('config',
                        __salt__['config.option']('service.config',
                                                  default='/etc/rc.conf'
                                                  )
                        )

    if not config:
        rcdir = '/etc/rc.conf.d'
        if not os.path.exists(rcdir) or not os.path.isdir(rcdir):
            log.error('{0} not exists'.format(rcdir))
            return False
        config = os.path.join(rcdir, rcvar.replace('_enable', ''))

    nlines = []
    edited = False

    if on:
        val = 'YES'
    else:
        val = 'NO'

    if os.path.exists(config):
        with salt.utils.fopen(config, 'r') as ifile:
            for line in ifile:
                if not line.startswith('{0}='.format(rcvar)):
                    nlines.append(line)
                    continue
                rest = line[len(line.split()[0]):]  # keep comments etc
                nlines.append('{0}="{1}"{2}'.format(rcvar, val, rest))
                edited = True
    if not edited:
        # Ensure that the file ends in a \n
        if len(nlines) > 1 and nlines[-1][-1] != '\n':
            nlines[-1] = '{0}\n'.format(nlines[-1])
        nlines.append('{0}="{1}"\n'.format(rcvar, val))

    with salt.utils.fopen(config, 'w') as ofile:
        ofile.writelines(nlines)

    return True


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    name
        service name

    config : /etc/rc.conf
        Config file for managing service. If config value is
        empty string, then /etc/rc.conf.d/<service> used.
        See man rc.conf(5) for details.

        Also service.config variable can be used to change default.

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    '''
    return _switch(name, True, **kwargs)


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    Arguments the same as for enable()

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    return _switch(name, False, **kwargs)


def enabled(name, **kwargs):
    '''
    Return True if the named service is enabled, false otherwise

    name
        Service name

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    '''
    if not available(name):
        log.error('Service {0} not found'.format(name))
        return False

    cmd = '{0} {1} rcvar'.format(_cmd(), name)

    for line in __salt__['cmd.run_stdout'](cmd, python_shell=False).splitlines():
        if '_enable="' not in line:
            continue
        _, state, _ = line.split('"', 2)
        return state.lower() in ('yes', 'true', 'on', '1')

    # probably will never reached
    return False


def disabled(name):
    '''
    Return True if the named service is enabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    '''
    return not enabled(name)


def available(name):
    '''
    Check that the given service is available.

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
    ret = []
    service = _cmd()
    for srv in __salt__['cmd.run']('{0} -l'.format(service)).splitlines():
        if not srv.isupper():
            ret.append(srv)
    return sorted(ret)


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    cmd = '{0} {1} onestart'.format(_cmd(), name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = '{0} {1} onestop'.format(_cmd(), name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    cmd = '{0} {1} onerestart'.format(_cmd(), name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def reload_(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    cmd = '{0} {1} onereload'.format(_cmd(), name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def status(name, sig=None):
    '''
    Return the status for a service (True or False).

    name
        Name of service

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    '''
    if sig:
        return bool(__salt__['status.pid'](sig))
    cmd = '{0} {1} onestatus'.format(_cmd(), name)
    return not __salt__['cmd.retcode'](cmd,
                                       python_shell=False,
                                       ignore_retcode=True)
