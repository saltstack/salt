# -*- coding: utf-8 -*-
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

[2] example upstart configuration file::

    lightdm
    emits login-session-start
    emits desktop-session-start
    emits desktop-shutdown
    start on ((((filesystem and runlevel [!06]) and started dbus) and (drm-device-added card0 PRIMARY_DEVICE_FOR_DISPLAY=1 or stopped udev-fallback-graphics)) or runlevel PREVLEVEL=S)
    stop on runlevel [016]

.. warning::
    This module should not be used on Red Hat systems. For these,
    the :mod:`rh_service <salt.modules.rh_service>` module should be
    used, as it supports the hybrid upstart/sysvinit system used in
    RHEL/CentOS 6.
'''
from __future__ import absolute_import

# Import python libs
import glob
import os
import re
import itertools

# Import salt libs
import salt.utils
import salt.modules.cmdmod
import salt.utils.systemd

__func_alias__ = {
    'reload_': 'reload'
}

# Define the module's virtual name
__virtualname__ = 'service'


def __virtual__():
    '''
    Only work on Ubuntu
    '''
    # Disable on these platforms, specific service modules exist:
    if salt.utils.systemd.booted(__context__):
        return False
    elif __grains__['os'] in ('Ubuntu', 'Linaro', 'elementary OS', 'Mint'):
        return __virtualname__
    elif __grains__['os'] in ('Debian', 'Raspbian'):
        debian_initctl = '/sbin/initctl'
        if os.path.isfile(debian_initctl):
            initctl_version = salt.modules.cmdmod._run_quiet(debian_initctl + ' version')
            if 'upstart' in initctl_version:
                return __virtualname__
    return False


def _find_utmp():
    '''
    Figure out which utmp file to use when determining runlevel.
    Sometimes /var/run/utmp doesn't exist, /run/utmp is the new hotness.
    '''
    result = {}
    # These are the likely locations for the file on Ubuntu
    for utmp in '/var/run/utmp', '/run/utmp':
        try:
            result[os.stat(utmp).st_mtime] = utmp
        except Exception:
            pass
    return result[sorted(result).pop()]


def _default_runlevel():
    '''
    Try to figure out the default runlevel.  It is kept in
    /etc/init/rc-sysinit.conf, but can be overridden with entries
    in /etc/inittab, or via the kernel command-line at boot
    '''
    # Try to get the "main" default.  If this fails, throw up our
    # hands and just guess "2", because things are horribly broken
    try:
        with salt.utils.fopen('/etc/init/rc-sysinit.conf') as fp_:
            for line in fp_:
                if line.startswith('env DEFAULT_RUNLEVEL'):
                    runlevel = line.split('=')[-1].strip()
    except Exception:
        return '2'

    # Look for an optional "legacy" override in /etc/inittab
    try:
        with salt.utils.fopen('/etc/inittab') as fp_:
            for line in fp_:
                if not line.startswith('#') and 'initdefault' in line:
                    runlevel = line.split(':')[1]
    except Exception:
        pass

    # The default runlevel can also be set via the kernel command-line.
    # Kinky.
    try:
        valid_strings = set(
            ('0', '1', '2', '3', '4', '5', '6', 's', 'S', '-s', 'single'))
        with salt.utils.fopen('/proc/cmdline') as fp_:
            for line in fp_:
                for arg in line.strip().split():
                    if arg in valid_strings:
                        runlevel = arg
                        break
    except Exception:
        pass

    return runlevel


def _runlevel():
    '''
    Return the current runlevel
    '''
    if 'upstart._runlevel' in __context__:
        return __context__['upstart._runlevel']
    out = __salt__['cmd.run'](['runlevel', '{0}'.format(_find_utmp())], python_shell=False)
    try:
        ret = out.split()[1]
    except IndexError:
        # The runlevel is unknown, return the default
        ret = _default_runlevel()
    __context__['upstart._runlevel'] = ret
    return ret


def _is_symlink(name):
    return os.path.abspath(name) != os.path.realpath(name)


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
    placed in /etc/init/[name].override.
    NOTE: An Upstart service can also be disabled by placing "manual"
    in /etc/init/[name].conf.
    '''
    files = ['/etc/init/{0}.conf'.format(name), '/etc/init/{0}.override'.format(name)]
    for file_name in itertools.ifilter(os.path.isfile, files):
        with salt.utils.fopen(file_name) as fp_:
            if re.search(r'^\s*manual', fp_.read(), re.MULTILINE):
                return True
    return False


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
    return not _service_is_upstart(name) and os.access(script, os.X_OK)


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


def _iter_service_names():
    '''
    Detect all of the service names available to upstart via init configuration
    files and via classic sysv init scripts
    '''
    found = set()
    for line in glob.glob('/etc/init.d/*'):
        name = os.path.basename(line)
        found.add(name)
        yield name
    for line in glob.glob('/etc/init/*.conf'):
        name = os.path.basename(line)[:-5]
        if name in found:
            continue
        yield name


def get_enabled():
    '''
    Return the enabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    ret = set()
    for name in _iter_service_names():
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

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    ret = set()
    for name in _iter_service_names():
        if _service_is_upstart(name):
            if _upstart_is_disabled(name):
                ret.add(name)
        else:
            if _service_is_sysv(name):
                if _sysv_is_disabled(name):
                    ret.add(name)
    return sorted(ret)


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
    Return all installed services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    return sorted(get_enabled() + get_disabled())


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    cmd = ['service', name, 'start']
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    cmd = ['service', name, 'stop']
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    cmd = ['service', name, 'restart']
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def full_restart(name):
    '''
    Do a full restart (stop/start) of the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.full_restart <service name>
    '''
    cmd = ['service', name, '--full-restart']
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def reload_(name):
    '''
    Reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    cmd = ['service', name, 'reload']
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def force_reload(name):
    '''
    Force-reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.force_reload <service name>
    '''
    cmd = ['service', name, 'force-reload']
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


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
    cmd = ['service', name, 'status']
    if _service_is_upstart(name):
        # decide result base on cmd output, thus ignore retcode,
        # which makes cmd output not at error lvl even when cmd fail.
        return 'start/running' in __salt__['cmd.run'](cmd, python_shell=False,
                                                      ignore_retcode=True)
    # decide result base on retcode, thus ignore output (set quite)
    # because there is no way to avoid logging at error lvl when
    # service is not running - retcode != 0 (which is totally relevant).
    return not bool(__salt__['cmd.retcode'](cmd, python_shell=False,
                                            quite=True))


def _get_service_exec():
    '''
    Debian uses update-rc.d to manage System-V style services.
    http://www.debian.org/doc/debian-policy/ch-opersys.html#s9.3.3
    '''
    executable = 'update-rc.d'
    salt.utils.check_or_die(executable)
    return executable


def _upstart_disable(name):
    '''
    Disable an Upstart service.
    '''
    if _upstart_is_disabled(name):
        return _upstart_is_disabled(name)
    override = '/etc/init/{0}.override'.format(name)
    with salt.utils.fopen(override, 'a') as ofile:
        ofile.write('manual\n')
    return _upstart_is_disabled(name)


def _upstart_enable(name):
    '''
    Enable an Upstart service.
    '''
    if _upstart_is_enabled(name):
        return _upstart_is_enabled(name)
    override = '/etc/init/{0}.override'.format(name)
    files = ['/etc/init/{0}.conf'.format(name), override]
    for file_name in itertools.ifilter(os.path.isfile, files):
        with salt.utils.fopen(file_name, 'r+') as fp_:
            new_text = re.sub(r'^\s*manual\n?', '', fp_.read(), 0, re.MULTILINE)
            fp_.seek(0)
            fp_.write(new_text)
            fp_.truncate()
    if os.access(override, os.R_OK) and os.path.getsize(override) == 0:
        os.unlink(override)
    return _upstart_is_enabled(name)


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    '''
    if _service_is_upstart(name):
        return _upstart_enable(name)
    executable = _get_service_exec()
    cmd = '{0} -f {1} defaults'.format(executable, name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def disable(name, **kwargs):
    '''
    Disable the named service from starting on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    if _service_is_upstart(name):
        return _upstart_disable(name)
    executable = _get_service_exec()
    cmd = [executable, '-f', name, 'remove']
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def enabled(name, **kwargs):
    '''
    Check to see if the named service is enabled to start on boot

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    '''
    if _service_is_upstart(name):
        return _upstart_is_disabled(name)
    else:
        if _service_is_sysv(name):
            return _sysv_is_disabled(name)
    return None
