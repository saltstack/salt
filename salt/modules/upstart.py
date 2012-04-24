'''
Module for the management of upstart systems. The Upstart system only supports
service starting, stopping and restarting.

Currently (as of Ubuntu 12.04) there is no tool available to disable
Upstart services (like update-rc.d). This[1] is the recommended way to
disable an Upstart service. So we assume that all Upstart services
that have not been disabled in this manner are enabled.

But this is broken because we do not check to see that the dependent
services are enabled. Otherwise we would have to do something like
parse the output of "initctl show-config" to determine if all service
dependencies are enabled to start on boot. For example, see the "start
on" condition for the lightdm service below[2]. And this would be too
hard. So we wait until the upstart developers have solved this
problem. :) This is to say that an Upstart service that is enabled may
not really be enabled.

Also, when an Upstart service is enabled, should the dependent
services be enabled too? Probably not. But there should be a notice
about this, at least.

[1] http://upstart.ubuntu.com/cookbook/#disabling-a-job-from-automatically-starting

[2] lightdm
  emits login-session-start
  emits desktop-session-start
  emits desktop-shutdown
  start on ((((filesystem and runlevel [!06]) and started dbus) and (drm-device-added card0 PRIMARY_DEVICE_FOR_DISPLAY=1 or stopped udev-fallback-graphics)) or runlevel PREVLEVEL=S)
  stop on runlevel [016]

DO NOT use this module on red hat systems, as red hat systems should use the
rh_service module, since red hat systems support chkconfig
'''

from salt import utils


def __virtual__():
    '''
    Only work on Ubuntu
    '''
    # Disable on these platforms, specific service modules exist:
    if __grains__['os'] == 'Ubuntu':
        return 'service'
    return False


def _runlevel():
    '''
    Return the current runlevel
    '''
    out = __salt__['cmd.run']('runlevel').strip()
    return out.split()[1]


def _service_is_upstart(name):
    if not __salt__['cmd.retcode']('test -f /etc/init/{0}.conf'.format(name)):
        return True
    return False


def _upstart_is_disabled(name):
    if not __salt__['cmd.retcode']('test -f /etc/init/{0}.conf.override'.format(name)):
        return True
    return False


def _upstart_is_enabled(name):
    return not _upstart_is_disabled(name)


def _service_is_sysv(name):
    if not __salt__['cmd.retcode']('test -f /etc/init.d/{0}'.format(name)):
        if not __salt__['cmd.retcode']('test -x /etc/init.d/{0}'.format(name)):
            return True
    return False


def _sysv_is_disabled(name):
    cmd = 'ls /etc/rc{0}.d/S*{1}'.format(_runlevel(), name)
    if not __salt__['cmd.run'](cmd).strip().endswith(name):
        return True
    return False


def _sysv_is_enabled(name):
    return not _sysv_is_disabled(name)


def get_enabled():
    '''
    Return the enabled services

    CLI Example::

        salt '*' service.get_enabled
    '''
    ret = set()
    cmd = '(cd /etc/init.d; ls -1 *)'
    lines = __salt__['cmd.run'](cmd).split('\n')
    for line in lines:
        name = line
        if _service_is_upstart(name):
            if _upstart_is_enabled(name):
                ret.add(name)
        else:
            if _service_is_sysv(name):
                if _sysv_is_enabled(name):
                    ret.add(name)
    return sorted(ret)


def get_disabled():
    '''
    Return the disabled services

    CLI Example::

        salt '*' service.get_disabled
    '''
    ret = set()
    cmd = '(cd /etc/init.d; ls -1 *)'
    lines = __salt__['cmd.run'](cmd).split('\n')
    for line in lines:
        name = line
        if _service_is_upstart(name):
            if _upstart_is_disabled(name):
                ret.add(name)
        else:
            if _service_is_sysv(name):
                if _sysv_is_disabled(name):
                    ret.add(name)
    return sorted(ret)


def get_all():
    '''
    Return all installed services

    CLI Example::

        salt '*' service.get_all
    '''
    return sorted(get_enabled() + get_disabled())


def start(name):
    '''
    Start the specified service

    CLI Example::

        salt '*' service.start <service name>
    '''
    cmd = 'service {0} start'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example::

        salt '*' service.stop <service name>
    '''
    cmd = 'service {0} stop'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name):
    '''
    Restart the named service

    CLI Example::

        salt '*' service.restart <service name>
    '''
    cmd = 'service {0} restart'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def status(name, sig=None):
    '''
    Return the status for a service, returns a bool whether the service is
    running.

    CLI Example::

        salt '*' service.status <service name>
    '''
    cmd = 'service {0} status'.format(name)
    return 'start/running' in __salt__['cmd.run'](cmd)


def _get_service_exec():
    executable = 'update-rc.d'
    utils.check_or_die(executable)
    return executable


def _upstart_disable(name):
    __salt__['cmd.run']('echo manual > /etc/init/{0}.conf.override'.format(name))
    return _upstart_is_disabled(name)


def _upstart_enable(name):
    __salt__['cmd.run']('rm -f /etc/init/{0}.conf.override'.format(name))
    return _upstart_is_enabled(name)


def enable(name):
    '''
    Enable the named service to start at boot

    CLI Example::

        salt '*' service.enable <service name>
    '''
    if _service_is_upstart(name):
        return _upstart_enable(name)
    executable = _get_service_exec()
    cmd = '{0} -f {1} defaults'.format(executable, name)
    return not __salt__['cmd.retcode'](cmd)


def disable(name):
    '''
    Disable the named service from starting on boot

    CLI Example::

        salt '*' service.disable <service name>
    '''
    if _service_is_upstart(name):
        return _upstart_disable(name)
    executable = _get_service_exec()
    cmd = '{0} -f {1} remove'.format(executable, name)
    return not __salt__['cmd.retcode'](cmd)


def enabled(name):
    '''
    Check to see if the named service is enabled to start on boot

    CLI Example::

        salt '*' service.enabled <service name>
    '''
    if _service_is_upstart(name):
        return _upstart_is_enabled(name)
    else:
        if _service_is_sysv(name):
            return _sysv_is_enabled(name)
    return None


def disabled(name):
    '''
    Check to see if the named service is disabled to start on boot

    CLI Example::

        salt '*' service.disabled <service name>
    '''
    if _service_is_upstart(name):
        return _upstart_is_disabled(name)
    else:
        if _service_is_sysv(name):
            return _sysv_is_disabled(name)
    return None
