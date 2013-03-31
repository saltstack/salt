'''
Service support for classic Red Hat type systems. This interface uses the
service command (so it is compatible with upstart systems) and the chkconfig
command.
'''

# Import python libs
import logging
import os

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only work on systems which default to systemd
    '''
    # Disable on these platforms, specific service modules exist:
    enable = [
        'RedHat',
        'CentOS',
        'Scientific',
        'CloudLinux',
        'Amazon',
        'Fedora',
        'ALT',
        'OEL',
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
    if name not in get_all() and __salt__['cmd.has_exec'](initscript_path):
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


def get_enabled():
    '''
    Return the enabled services

    CLI Example::

        salt '*' service.get_enabled
    '''
    rlevel = _runlevel()
    ret = set()
    cmd = '/sbin/chkconfig --list'
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        if len(comps) > 3 and '{0}:on'.format(rlevel) in line:
            ret.add(comps[0])
        elif len(comps) < 3 and comps[1] and comps[1] == 'on':
            ret.add(comps[0].strip(':'))
    return sorted(ret)


def get_disabled():
    '''
    Return the disabled services

    CLI Example::

        salt '*' service.get_disabled
    '''
    rlevel = _runlevel()
    ret = set()
    cmd = '/sbin/chkconfig --list'
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        comps = line.split()
        if not comps:
            continue
        if not '{0}:on'.format(rlevel) in line:
            ret.add(comps[0])
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
    _add_custom_initscript(name)
    cmd = '/sbin/service {0} start'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def stop(name):
    '''
    Stop the specified service

    CLI Example::

        salt '*' service.stop <service name>
    '''
    _add_custom_initscript(name)
    cmd = '/sbin/service {0} stop'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def restart(name, **kwargs):
    '''
    Restart the named service

    CLI Example::

        salt '*' service.restart <service name>
    '''
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
    _add_custom_initscript(name)
    if sig:
        return bool(__salt__['status.pid'](sig))
    cmd = '/sbin/service {0} status'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def enable(name, **kwargs):
    '''
    Enable the named service to start at boot

    CLI Example::

        salt '*' service.enable <service name>
    '''
    _add_custom_initscript(name)
    cmd = '/sbin/chkconfig {0} on'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def disable(name, **kwargs):
    '''
    Disable the named service to start at boot

    CLI Example::

        salt '*' service.disable <service name>
    '''
    _add_custom_initscript(name)
    cmd = '/sbin/chkconfig {0} off'.format(name)
    return not __salt__['cmd.retcode'](cmd)


def enabled(name):
    '''
    Check to see if the named service is enabled to start on boot

    CLI Example::

        salt '*' service.enabled <service name>
    '''
    _add_custom_initscript(name)
    return name in get_enabled()


def disabled(name):
    '''
    Check to see if the named service is disabled to start on boot

    CLI Example::

        salt '*' service.disabled <service name>
    '''
    _add_custom_initscript(name)
    return name in get_disabled()
