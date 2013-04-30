'''
Service support for RHEL-based systems. This interface uses the service and
chkconfig commands, and for upstart support uses helper functions from the
upstart module, as well as the ``start``, ``stop``, and ``status`` commands.
'''

# Import python libs
import glob
import logging
import os

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

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
    Only work on systems which default to systemd
    '''
    # Enable on these platforms only.
    enable = [
        'RedHat',
        'CentOS',
        'Scientific',
        'CloudLinux',
        'Amazon',
        'Fedora',
        'ALT',
        'OEL',
        'SUSE  Enterprise Server'
    ]
    if __grains__['os'] in enable:
        if __grains__['os'] == 'Fedora':
            if __grains__.get('osrelease', 0) > 15:
                return False
        return 'service'
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


def _add_custom_initscript(name):
    '''
    If the passed service name is not in the output from get_all(), runs a
    'chkconfig --add' so that it is available.
    '''
    initscript_path = os.path.join('/etc/init.d', name)
    if name not in get_all() and os.access(initscript_path, os.X_OK):
        cmd = '/sbin/chkconfig --add {0}'.format(name)
        if __salt__['cmd.retcode'](cmd):
            log.error('Unable to add initscript "{0}"'.format(name))
        else:
            log.info('Added initscript "{0}"'.format(name))
            # Disable initscript by default. If a user wants it enabled, he/she
            # can configure that in a state. Since we're adding the service
            # automagically, we shouldn't also enable it, as the user may not
            # be aware that the service was added to chkconfig and thus would
            # not be expecting it to start on boot (which is the default).
            cmd = '/sbin/chkconfig {0} off'.format(name)
            __salt__['cmd.run'](cmd)


def _sysv_is_enabled(chkconfig_line, rlevel):
    '''
    Given a list of columns from a line of 'chkconfig --list' output, and the
    runlevel, return True if enabled. Otherwise, return False.
    '''
    if len(chkconfig_line) > 3 and '{0}:on'.format(rlevel) in chkconfig_line:
        return True
    elif len(chkconfig_line) < 3 and chkconfig_line[1] \
            and chkconfig_line[1] == 'on':
        return True
    return False


def _service_is_upstart(name):
    '''
    Return true if the service is an upstart service, otherwise return False.
    '''
    return name in get_all(limit='upstart')


def _services():
    '''
    Return a dict of services and their types (sysv or upstart), as well
    as whether or not the service is enabled.
    '''
    if 'service.all' in __context__:
        return __context__['service.all']

    # First, parse sysvinit services from chkconfig
    rlevel = _runlevel()
    ret = {}
    for line in __salt__['cmd.run']('/sbin/chkconfig --list').splitlines():
        cols = line.split()
        try:
            name = cols[0]
        except IndexError:
            continue
        if name in ret:
            continue
        ret.setdefault(name, {})['type'] = 'sysvinit'
        ret[name]['enabled'] = _sysv_is_enabled(cols, rlevel)
    if HAS_UPSTART:
        for line in glob.glob('/etc/init/*.conf'):
            name = os.path.basename(line)[:-5]
            if name in ret:
                continue
            ret.setdefault(name, {})['type'] = 'upstart'
            ret[name]['enabled'] = _upstart_is_enabled(name)
    __context__['service.all'] = ret
    return ret


def get_enabled(limit=''):
    '''
    Return the enabled services. Use the ``limit`` param to restrict results
    to services of that type.

    CLI Examples::

        salt '*' service.get_enabled
        salt '*' service.get_enabled limit=upstart
        salt '*' service.get_enabled limit=sysvinit
    '''
    limit = limit.lower()
    if limit in ('upstart', 'sysvinit'):
        return sorted([x for x, y in _services().iteritems()
                       if y['enabled'] and y['type'] == limit])
    else:
        return sorted([x for x, y in _services().iteritems()
                       if y['enabled']])


def get_disabled(limit=''):
    '''
    Return the disabled services. Use the ``limit`` param to restrict results
    to services of that type.

    CLI Example::

        salt '*' service.get_disabled
        salt '*' service.get_disabled limit=upstart
        salt '*' service.get_disabled limit=sysvinit
    '''
    limit = limit.lower()
    if limit in ('upstart', 'sysvinit'):
        return sorted([x for x, y in _services().iteritems()
                       if not y['enabled'] and y['type'] == limit])
    else:
        return sorted([x for x, y in _services().iteritems()
                       if not y['enabled']])


def get_all(limit=''):
    '''
    Return all installed services. Use the ``limit`` param to restrict results
    to services of that type.

    CLI Example::

        salt '*' service.get_all
        salt '*' service.get_all limit=upstart
        salt '*' service.get_all limit=sysvinit
    '''
    limit = limit.lower()
    if limit in ('upstart', 'sysvinit'):
        return sorted([x for x, y in _services().iteritems()
                       if y['type'] == limit])
    else:
        return sorted([x for x, y in _services().iteritems()])


def start(name):
    '''
    Start the specified service

    CLI Example::

        salt '*' service.start <service name>
    '''
    if _services().get(name, {}).get('type', '') == 'upstart':
        cmd = 'start {0}'.format(name)
    else:
        _add_custom_initscript(name)
        cmd = '/sbin/service {0} start'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example::

        salt '*' service.stop <service name>
    '''
    if _service_is_upstart(name):
        cmd = 'stop {0}'.format(name)
    else:
        _add_custom_initscript(name)
        cmd = '/sbin/service {0} stop'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name, **kwargs):
    '''
    Restart the named service

    CLI Example::

        salt '*' service.restart <service name>
    '''
    if _service_is_upstart(name):
        cmd = 'restart {0}'.format(name)
    else:
        _add_custom_initscript(name)
        cmd = '/sbin/service {0} restart'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def status(name, sig=None):
    '''
    Return the status for a service, returns a bool whether the service is
    running.

    CLI Example::

        salt '*' service.status <service name>
    '''
    if _service_is_upstart(name):
        cmd = 'status {0}'.format(name)
        return 'start/running' in __salt__['cmd.run'](cmd)
    _add_custom_initscript(name)
    if sig:
        return bool(__salt__['status.pid'](sig))
    cmd = '/sbin/service {0} status'.format(name)
    return __salt__['cmd.retcode'](cmd) == 0


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example::

        salt '*' service.enable <service name>
    '''
    if _service_is_upstart(name):
        return _upstart_enable(name)
    _add_custom_initscript(name)
    cmd = '/sbin/chkconfig {0} on'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example::

        salt '*' service.disable <service name>
    '''
    if _service_is_upstart(name):
        return _upstart_disable(name)
    _add_custom_initscript(name)
    cmd = '/sbin/chkconfig {0} off'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def enabled(name):
    '''
    Check to see if the named service is enabled to start on boot

    CLI Example::

        salt '*' service.enabled <service name>
    '''
    if _service_is_upstart(name):
        return _upstart_is_enabled(name)
    _add_custom_initscript(name)
    return name in get_enabled()


def disabled(name):
    '''
    Check to see if the named service is disabled to start on boot

    CLI Example::

        salt '*' service.disabled <service name>
    '''
    if _service_is_upstart(name):
        return not _upstart_is_enabled(name)
    _add_custom_initscript(name)
    return name in get_disabled()
