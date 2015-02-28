# -*- coding: utf-8 -*-
'''
Service support for RHEL-based systems, including support for both upstart and sysvinit
'''

# Import python libs
import glob
import logging
import os
import stat

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

__func_alias__ = {
    'reload_': 'reload'
}

# Define the module's virtual name
__virtualname__ = 'service'

# Import upstart module if needed
HAS_UPSTART = False
if salt.utils.which('initctl'):
    try:
        # Don't re-invent the wheel, import the helper functions from the
        # upstart module.
        from salt.modules.upstart \
            import _upstart_enable, _upstart_disable, _upstart_is_enabled
    except Exception as exc:
        log.error('Unable to import helper functions from '
                  'salt.modules.upstart: {0}'.format(exc))
    else:
        HAS_UPSTART = True


def __virtual__():
    '''
    Only work on select distros which still use Red Hat's /usr/bin/service for
    management of either sysvinit or a hybrid sysvinit/upstart init system.
    '''
    # Enable on these platforms only.
    enable = set((
        'RedHat',
        'CentOS',
        'ScientificLinux',
        'CloudLinux',
        'Amazon',
        'Fedora',
        'ALT',
        'OEL',
        'SUSE  Enterprise Server',
        'SUSE',
        'McAfee  OS Server'
    ))
    if __grains__['os'] in enable:
        if __grains__['os'] == 'SUSE':
            if __grains__['osrelease'].startswith('11'):
                return __virtualname__
            else:
                return False
        try:
            osrelease = float(__grains__.get('osrelease', 0))
        except ValueError:
            return False
        if __grains__['os'] == 'Fedora':
            if osrelease > 15:
                return False
        if __grains__['os'] in ('RedHat', 'CentOS', 'ScientificLinux'):
            if osrelease >= 7:
                return False
        return __virtualname__
    return False


def _runlevel():
    '''
    Return the current runlevel
    '''
    out = __salt__['cmd.run']('/sbin/runlevel')
    # unknown will be returned while inside a kickstart environment, since
    # this is usually a server deployment it should be safe to assume runlevel
    # 3.  If not all service related states will throw an out of range
    # exception here which will cause other functions to fail.
    if 'unknown' in out:
        return '3'
    else:
        return out.split()[1]


def _chkconfig_add(name):
    '''
    Run 'chkconfig --add' for a service whose script is installed in
    /etc/init.d.  The service is initially configured to be disabled at all
    run-levels.
    '''
    cmd = '/sbin/chkconfig --add {0}'.format(name)
    if __salt__['cmd.retcode'](cmd, python_shell=False) == 0:
        log.info('Added initscript "{0}" to chkconfig'.format(name))
        return True
    else:
        log.error('Unable to add initscript "{0}" to chkconfig'.format(name))
        return False


def _service_is_upstart(name):
    '''
    Return True if the service is an upstart service, otherwise return False.
    '''
    return HAS_UPSTART and os.path.exists('/etc/init/{0}.conf'.format(name))


def _service_is_sysv(name):
    '''
    Return True if the service is a System V service (includes those managed by
    chkconfig); otherwise return False.
    '''
    try:
        # Look for user-execute bit in file mode.
        return bool(os.stat(
            os.path.join('/etc/init.d', name)).st_mode & stat.S_IXUSR)
    except OSError:
        return False


def _service_is_chkconfig(name):
    '''
    Return True if the service is managed by chkconfig.
    '''
    cmdline = '/sbin/chkconfig --list {0}'.format(name)
    return __salt__['cmd.retcode'](cmdline, python_shell=False, ignore_retcode=True) == 0


def _sysv_is_enabled(name, runlevel=None):
    '''
    Return True if the sysv (or chkconfig) service is enabled for the specified
    runlevel; otherwise return False.  If `runlevel` is None, then use the
    current runlevel.
    '''
    # Try chkconfig first.
    result = _chkconfig_is_enabled(name, runlevel)
    if result:
        return True

    if runlevel is None:
        runlevel = _runlevel()
    return (
        len(glob.glob('/etc/rc.d/rc{0}.d/S??{1}'.format(runlevel, name))) > 0)


def _chkconfig_is_enabled(name, runlevel=None):
    '''
    Return True if the service is enabled according to chkconfig; otherwise
    return False.  If `runlevel` is None, then use the current runlevel.
    '''
    cmdline = '/sbin/chkconfig --list {0}'.format(name)
    result = __salt__['cmd.run_all'](cmdline, python_shell=False)
    if result['retcode'] == 0:
        cols = result['stdout'].splitlines()[0].split()
        try:
            if cols[0].strip(':') == name:
                if runlevel is None:
                    runlevel = _runlevel()
                if len(cols) > 3 and '{0}:on'.format(runlevel) in cols:
                    return True
                elif len(cols) < 3 and cols[1] and cols[1] == 'on':
                    return True
        except IndexError:
            pass
    return False


def _sysv_enable(name):
    '''
    Enable the named sysv service to start at boot.  The service will be enabled
    using chkconfig with default run-levels if the service is chkconfig
    compatible.  If chkconfig is not available, then this will fail.
    '''
    if not _service_is_chkconfig(name) and not _chkconfig_add(name):
        return False
    cmd = '/sbin/chkconfig {0} on'.format(name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def _sysv_disable(name):
    '''
    Disable the named sysv service from starting at boot.  The service will be
    disabled using chkconfig with default run-levels if the service is chkconfig
    compatible; otherwise, the service will be disabled for the current
    run-level only.
    '''
    if not _service_is_chkconfig(name) and not _chkconfig_add(name):
        return False
    cmd = '/sbin/chkconfig {0} off'.format(name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def _upstart_services():
    '''
    Return list of upstart services.
    '''
    if HAS_UPSTART:
        return [os.path.basename(name)[:-5]
            for name in glob.glob('/etc/init/*.conf')]
    else:
        return []


def _sysv_services():
    '''
    Return list of sysv services.
    '''
    ret = []
    return [name for name in os.listdir('/etc/init.d')
        if _service_is_sysv(name)]


def get_enabled(limit=''):
    '''
    Return the enabled services. Use the ``limit`` param to restrict results
    to services of that type.

    CLI Examples:

    .. code-block:: bash

        salt '*' service.get_enabled
        salt '*' service.get_enabled limit=upstart
        salt '*' service.get_enabled limit=sysvinit
    '''
    limit = limit.lower()
    if limit == 'upstart':
        return sorted(name for name in _upstart_services()
            if _upstart_is_enabled(name))
    elif limit == 'sysvinit':
        runlevel = _runlevel()
        return sorted(name for name in _sysv_services()
            if _sysv_is_enabled(name, runlevel))
    else:
        runlevel = _runlevel()
        return sorted(
            [name for name in _upstart_services()
                if _upstart_is_enabled(name)]
            + [name for name in _sysv_services()
            if _sysv_is_enabled(name, runlevel)])


def get_disabled(limit=''):
    '''
    Return the disabled services. Use the ``limit`` param to restrict results
    to services of that type.

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
        salt '*' service.get_disabled limit=upstart
        salt '*' service.get_disabled limit=sysvinit
    '''
    limit = limit.lower()
    if limit == 'upstart':
        return sorted(name for name in _upstart_services()
            if not _upstart_is_enabled(name))
    elif limit == 'sysvinit':
        runlevel = _runlevel()
        return sorted(name for name in _sysv_services()
            if not _sysv_is_enabled(name, runlevel))
    else:
        runlevel = _runlevel()
        return sorted(
            [name for name in _upstart_services()
                if not _upstart_is_enabled(name)]
            + [name for name in _sysv_services()
            if not _sysv_is_enabled(name, runlevel)])


def get_all(limit=''):
    '''
    Return all installed services. Use the ``limit`` param to restrict results
    to services of that type.

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
        salt '*' service.get_all limit=upstart
        salt '*' service.get_all limit=sysvinit
    '''
    limit = limit.lower()
    if limit == 'upstart':
        return sorted(_upstart_services())
    elif limit == 'sysvinit':
        return sorted(_sysv_services())
    else:
        return sorted(_sysv_services() + _upstart_services())


def available(name, limit=''):
    '''
    Return True if the named service is available.  Use the ``limit`` param to
    restrict results to services of that type.

    CLI Examples:

    .. code-block:: bash

        salt '*' service.available sshd
        salt '*' service.available sshd limit=upstart
        salt '*' service.available sshd limit=sysvinit
    '''
    if limit == 'upstart':
        return _service_is_upstart(name)
    elif limit == 'sysvinit':
        return _service_is_sysv(name)
    else:
        return _service_is_upstart(name) or _service_is_sysv(name) or _service_is_chkconfig(name)


def missing(name, limit=''):
    '''
    The inverse of service.available.
    Return True if the named service is not available.  Use the ``limit`` param to
    restrict results to services of that type.

    CLI Examples:

    .. code-block:: bash

        salt '*' service.missing sshd
        salt '*' service.missing sshd limit=upstart
        salt '*' service.missing sshd limit=sysvinit
    '''
    if limit == 'upstart':
        return not _service_is_upstart(name)
    elif limit == 'sysvinit':
        return not _service_is_sysv(name)
    else:
        if _service_is_upstart(name) or _service_is_sysv(name):
            return False
        else:
            return True


def start(name):
    '''
    Start the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    if _service_is_upstart(name):
        cmd = 'start {0}'.format(name)
    else:
        cmd = '/sbin/service {0} start'.format(name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def stop(name):
    '''
    Stop the specified service

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    if _service_is_upstart(name):
        cmd = 'stop {0}'.format(name)
    else:
        cmd = '/sbin/service {0} stop'.format(name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def restart(name):
    '''
    Restart the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    if _service_is_upstart(name):
        cmd = 'restart {0}'.format(name)
    else:
        cmd = '/sbin/service {0} restart'.format(name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def reload_(name):
    '''
    Reload the named service

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    if _service_is_upstart(name):
        cmd = 'reload {0}'.format(name)
    else:
        cmd = '/sbin/service {0} reload'.format(name)
    return not __salt__['cmd.retcode'](cmd, python_shell=False)


def status(name, sig=None):
    '''
    Return the status for a service, returns a bool whether the service is
    running.

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    '''
    if _service_is_upstart(name):
        cmd = 'status {0}'.format(name)
        return 'start/running' in __salt__['cmd.run'](cmd, python_shell=False)
    if sig:
        return bool(__salt__['status.pid'](sig))
    cmd = '/sbin/service {0} status'.format(name)
    return __salt__['cmd.retcode'](cmd, python_shell=False, ignore_retcode=True) == 0


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    '''
    if _service_is_upstart(name):
        return _upstart_enable(name)
    else:
        return _sysv_enable(name)


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    if _service_is_upstart(name):
        return _upstart_disable(name)
    else:
        return _sysv_disable(name)


def enabled(name):
    '''
    Check to see if the named service is enabled to start on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    '''
    if _service_is_upstart(name):
        return _upstart_is_enabled(name)
    else:
        return _sysv_is_enabled(name)


def disabled(name):
    '''
    Check to see if the named service is disabled to start on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    '''
    if _service_is_upstart(name):
        return not _upstart_is_enabled(name)
    else:
        return not _sysv_is_enabled(name)
