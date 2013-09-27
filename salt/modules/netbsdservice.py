# -*- coding: utf-8 -*-
'''
The service module for NetBSD
'''

# Import python libs
import os
import glob

__func_alias__ = {
    'reload_': 'reload'
}


def __virtual__():
    '''
    Only work on NetBSD
    '''
    if __grains__['os'] == 'NetBSD' and os.path.exists('/etc/rc.subr'):
        return 'service'
    return False


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    cmd = '/etc/rc.d/{0} onestart'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = '/etc/rc.d/{0} onestop'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    cmd = '/etc/rc.d/{0} onerestart'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def reload_(name):
    '''
    Reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    cmd = '/etc/rc.d/{0} onereload'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def force_reload(name):
    '''
    Force-reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.force_reload <service name>
    '''
    cmd = '/etc/rc.d/{0} forcereload'.format(name)
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
    cmd = '/etc/rc.d/{0} onestatus'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def _get_svc(rcd, service_status):
    '''
    Returns a unique service status
    '''
    ena = None
    lines = __salt__['cmd.run']('{0} rcvar'.format(rcd)).splitlines()
    for rcvar in lines:
        if rcvar.startswith('$') and '={0}'.format(service_status) in rcvar:
            ena = 'yes'
        elif rcvar.startswith('#'):
            svc = rcvar.split(' ', 1)[1]
        else:
            continue

    if ena and svc:
        return svc
    return None


def _get_svc_list(service_status):
    '''
    Returns all service statuses
    '''
    prefix = '/etc/rc.d/'
    ret = set()
    lines = glob.glob('{0}*'.format(prefix))
    for line in lines:
        svc = _get_svc(line, service_status)
        if svc is not None:
            ret.add(svc)

    return sorted(ret)


def get_enabled():
    '''
    Return a list of service that are enabled on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    return _get_svc_list('YES')


def get_disabled():
    '''
    Return a set of services that are installed but disabled

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    return _get_svc_list('NO')


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
    Return all available boot services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    return _get_svc_list('')


def _rcconf_status(name, service_status):
    '''
    Modifies /etc/rc.conf so a service is started or not at boot time and
    can be started via /etc/rc.d/<service>
    '''
    rcconf = '/etc/rc.conf'
    rxname = '^{0}=.*'.format(name)
    newstatus = '{0}={1}'.format(name, service_status)
    ret = __salt__['cmd.retcode']('grep \'{0}\' {1}'.format(rxname, rcconf))
    if ret == 0:  # service found in rc.conf, modify its status
        # NetBSD sed does not support -i flag, call sed by hand
        cmd = 'cp -f {0} {0}.bak && sed -E -e s/{1}/{2}/g {0}.bak > {0}'
        ret = __salt__['cmd.run'](cmd.format(rcconf, rxname, newstatus))
    else:
        ret = __salt__['file.append'](rcconf, newstatus)

    return ret


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    '''
    return _rcconf_status(name, 'YES')


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    return _rcconf_status(name, 'NO')


def enabled(name):
    '''
    Return True if the named service is enabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    '''
    return _get_svc('/etc/rc.d/{0}'.format(name), 'YES')


def disabled(name):
    '''
    Return True if the named service is enabled, false otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    '''
    return _get_svc('/etc/rc.d/{0}'.format(name), 'NO')


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
