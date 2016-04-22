# -*- coding: utf-8 -*-
'''
Service support for Debian systems (uses update-rc.d and /sbin/service)

.. important::
    If you feel that Salt should be using this module to manage services on a
    minion, and it is using a different module (or gives an error similar to
    *'service.start' is not available*), see :ref:`here
    <module-provider-override>`.
'''
from __future__ import absolute_import

# Import python libs
import logging
import glob
import re

# Import 3rd-party libs
# pylint: disable=import-error
from salt.ext.six.moves import shlex_quote as _cmd_quote
# pylint: enable=import-error

# Import salt libs
import salt.utils.systemd

__func_alias__ = {
    'reload_': 'reload'
}

# Define the module's virtual name
__virtualname__ = 'service'

log = logging.getLogger(__name__)


_DEFAULT_VER = '7.0.0'


def __virtual__():
    '''
    Only work on Debian and when systemd isn't running
    '''
    if __grains__['os'] in ('Debian', 'Raspbian', 'Devuan') and not salt.utils.systemd.booted(__context__):
        return __virtualname__
    else:
        return (False, 'The debian_service module could not be loaded: '
                'unsupported OS family and/or systemd running.')


def _service_cmd(*args):
    osmajor = _osrel()[0]
    if osmajor < '6':
        cmd = '/etc/init.d/{0} {1}'.format(args[0], ' '.join(args[1:]))
    else:
        cmd = 'service {0} {1}'.format(args[0], ' '.join(args[1:]))
    return cmd


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
    cmd = _service_cmd(name, 'start')
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = _service_cmd(name, 'stop')
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    cmd = _service_cmd(name, 'restart')
    return not __salt__['cmd.retcode'](cmd)


def reload_(name):
    '''
    Reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    cmd = _service_cmd(name, 'reload')
    return not __salt__['cmd.retcode'](cmd)


def force_reload(name):
    '''
    Force-reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.force_reload <service name>
    '''
    cmd = _service_cmd(name, 'force-reload')
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
    cmd = _service_cmd(name, 'status')
    return not __salt__['cmd.retcode'](cmd)


def _osrel():
    osrel = __grains__.get('osrelease', _DEFAULT_VER)
    if not osrel:
        osrel = _DEFAULT_VER
    return osrel


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    '''
    osmajor = _osrel()[0]
    if osmajor < '6':
        cmd = 'update-rc.d -f {0} defaults 99'.format(_cmd_quote(name))
    else:
        cmd = 'update-rc.d {0} enable'.format(_cmd_quote(name))
    try:
        if int(osmajor) >= 6:
            cmd = 'insserv {0} && '.format(_cmd_quote(name)) + cmd
    except ValueError:
        osrel = _osrel()
        if osrel == 'testing/unstable' or osrel == 'unstable' or osrel.endswith("/sid"):
            cmd = 'insserv {0} && '.format(_cmd_quote(name)) + cmd
    return not __salt__['cmd.retcode'](cmd, python_shell=True)


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    osmajor = _osrel()[0]
    if osmajor < '6':
        cmd = 'update-rc.d -f {0} remove'.format(name)
    else:
        cmd = 'update-rc.d {0} disable'.format(name)
    return not __salt__['cmd.retcode'](cmd)


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
