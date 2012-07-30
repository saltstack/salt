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

import glob
import os

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
    TODO: Should this return the "default" runlevel? For example, bad
    things will likely happen when 'salt' is run in single-user mode.
    '''
    out = __salt__['cmd.run']('runlevel').strip()
    return out.split()[1]


def _is_symlink(name):
    return not os.path.abspath(name) == os.path.realpath(name)


def _service_is_upstart(name):
    '''
    From "Writing Jobs" at
    http://upstart.ubuntu.com/getting-started.html:

    Jobs are defined in files placed in /etc/init, the name of the job
    is the filename under this directory without the .conf extension.
    '''
    return os.access('/etc/init/{0}.conf'.format(name), os.R_OK)


def _upstart_is_disabled(name):
    '''
    An Upstart service is assumed disabled if a manual stanza is
    placed in /etc/init/[name].conf.override.
    NOTE: An Upstart service can also be disabled by placing "manual"
    in /etc/init/[name].conf.
    '''
    return os.access('/etc/init/{0}.conf.override'.format(name), os.R_OK)


def _upstart_is_enabled(name):
    '''
    Assume that if an Upstart service is not disabled then it must be
    enabled.
    '''
    return not _upstart_is_disabled(name)


def _service_is_sysv(name):
    '''
    A System-V style service will have a control script in
    /etc/init.d. We make sure to skip over symbolic links that point
    to Upstart's /lib/init/upstart-job, and anything that isn't an
    executable, like README or skeleton.
    '''
    script = '/etc/init.d/{0}'.format(name)
    if not _is_symlink(script):
        return os.access(script, os.X_OK)
    return False


def _sysv_is_disabled(name):
    '''
    A System-V style service is assumed disabled if there is no
    start-up link (starts with "S") to its script in /etc/init.d in
    the current runlevel.
    '''
    return not bool(glob.glob('/etc/rc{0}.d/S*{1}'.format(_runlevel(), name)))


def _sysv_is_enabled(name):
    '''
    Assume that if a System-V style service is not disabled then it
    must be enabled.
    '''
    return not _sysv_is_disabled(name)


def get_enabled():
    '''
    Return the enabled services

    CLI Example::

        salt '*' service.get_enabled
    '''
    ret = set()
    for line in glob.glob('/etc/init.d/*'):
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
    for line in glob.glob('/etc/init.d/*'):
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


def reload(name):
    '''
    Reload the named service

    CLI Example::

        salt '*' service.reload <service name>
    '''
    cmd = 'service {0} reload'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def status(name, sig=None):
    '''
    Return the status for a service, returns a bool whether the service is
    running.

    CLI Example::

        salt '*' service.status <service name>
    '''
    cmd = 'service {0} status'.format(name)
    if _service_is_upstart(name):
        return 'start/running' in __salt__['cmd.run'](cmd)
    return not bool(__salt__['cmd.retcode'](cmd))


def _get_service_exec():
    '''
    Debian uses update-rc.d to manage System-V style services.
    http://www.debian.org/doc/debian-policy/ch-opersys.html#s9.3.3
    '''
    executable = 'update-rc.d'
    utils.check_or_die(executable)
    return executable


def _upstart_disable(name):
    '''
    Disable an Upstart service.
    '''
    override = '/etc/init/{0}.conf.override'.format(name)
    with file(override, 'w') as fd:
        fd.write('manual')
    return _upstart_is_disabled(name)


def _upstart_enable(name):
    '''
    Enable an Upstart service.
    '''
    override = '/etc/init/{0}.conf.override'.format(name)
    if os.access(override, os.R_OK):
        os.unlink(override)
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
