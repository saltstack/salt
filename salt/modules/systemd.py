'''
Provide the service module for systemd
'''
# Import Python libs
import re
# Import Salt libs
import salt.utils

LOCAL_CONFIG_PATH = '/etc/systemd/system'
VALID_UNIT_TYPES = ['service','socket', 'device', 'mount', 'automount',
                    'swap', 'target', 'path', 'timer']

def __virtual__():
    '''
    Only work on systems which default to systemd
    '''
    enable = (
            'Arch',
            'openSUSE',
            )
    if __grains__['os'] == 'Fedora' and __grains__['osrelease'] > 15:
        return 'service'
    elif __grains__['os'] in enable:
        return 'service'
    return False


def _canonical_unit_name(name):
    '''
    Build a canonical unit name treating unit names without one
    of the valid suffixes as a service.
    '''
    if any(name.endswith(suffix) for suffix in VALID_UNIT_TYPES):
        return name
    return '{0}.service'.format(name)


def _canonical_template_unit_name(name):
    '''
    Build a canonical unit name for unit instances based on templates.
    '''
    return re.sub(r'@.+?(\.|$)', r'@\1', name)


def _systemctl_cmd(action, name):
    '''
    Build a systemctl command line. Treat unit names without one
    of the valid suffixes as a service.
    '''
    return 'systemctl {0} {1}'.format(action, _canonical_unit_name(name))

def _get_all_unit_files():
    '''
    Get all unit files and their state. Unit files ending in .service
    are normalized so that they can be referenced without a type suffix.
    '''
    rexp = re.compile('(?m)^(?P<name>.+)\.(?P<type>' +
                      '|'.join(VALID_UNIT_TYPES) +
                      ')\s+(?P<state>.+)$')

    out = __salt__['cmd.run_stdout'](
            'systemctl --full list-unit-files | col -b'
    )

    ret = {}
    for match in rexp.finditer(out):
        name = match.group('name')
        if match.group('type') != 'service':
            name += '.' + match.group('type')
        ret[name] = match.group('state')
    return ret


def get_enabled():
    '''
    Return a list of all enabled services

    CLI Example::

        salt '*' service.get_enabled
    '''
    ret = []
    for name, state in _get_all_unit_files().iteritems():
        if state == 'enabled':
            ret.append(name)
    return sorted(ret)


def get_disabled():
    '''
    Return a list of all disabled services

    CLI Example::

        salt '*' service.get_disabled
    '''
    ret = []
    for name, state in _get_all_unit_files().iteritems():
        if state == 'disabled':
            ret.append(name)
    return sorted(ret)


def get_all():
    '''
    Return a list of all available services

    CLI Example::

        salt '*' service.get_all
    '''
    return sorted(_get_all_unit_files().keys())


def available(name):
    '''
    Check that the given service is available taking into account
    template units.
    '''
    return _canonical_template_unit_name(name) in get_all()


def start(name):
    '''
    Start the specified service with systemd

    CLI Example::

        salt '*' service.start <service name>
    '''
    return not __salt__['cmd.retcode'](_systemctl_cmd('start', name))


def stop(name):
    '''
    Stop the specified service with systemd

    CLI Example::

        salt '*' service.stop <service name>
    '''
    return not __salt__['cmd.retcode'](_systemctl_cmd('stop', name))


def restart(name):
    '''
    Restart the specified service with systemd

    CLI Example::

        salt '*' service.restart <service name>
    '''
    if name == 'salt-minion':
        salt.utils.daemonize_if(__opts__)
    return not __salt__['cmd.retcode'](_systemctl_cmd('restart', name))


def reload(name):
    '''
    Reload the specified service with systemd

    CLI Example::

        salt '*' service.reload <service name>
    '''
    return not __salt__['cmd.retcode'](_systemctl_cmd('reload', name))


def force_reload(name):
    '''
    Force-reload the specified service with systemd

    CLI Example::

        salt '*' service.force_reload <service name>
    '''
    return not __salt__['cmd.retcode'](_systemctl_cmd('force-reload', name))


# The unused sig argument is required to maintain consistency in the state
# system
def status(name, sig=None):
    '''
    Return the status for a service via systemd, returns a bool
    whether the service is running.

    CLI Example::

        salt '*' service.status <service name>
    '''
    cmd = 'systemctl is-active {0}'.format(_canonical_unit_name(name))
    return not __salt__['cmd.retcode'](cmd)


def enable(name, **kwargs):
    '''
    Enable the named service to start when the system boots

    CLI Example::

        salt '*' service.enable <service name>
    '''
    return not __salt__['cmd.retcode'](_systemctl_cmd('enable', name))


def disable(name, **kwargs):
    '''
    Disable the named service to not start when the system boots

    CLI Example::

        salt '*' service.disable <service name>
    '''
    return not __salt__['cmd.retcode'](_systemctl_cmd('disable', name))


def _templated_instance_enabled(name):
    '''
    Services instantiated based on templates can not be checked with
    systemctl is-enabled. Presence of the actual symlinks is checked
    as a fall-back.
    '''
    if '@' not in name:
        return False
    find_unit_by_name = 'find {0} -name {1} -type l -print -quit'
    return len(__salt__['cmd.run'](find_unit_by_name.format(LOCAL_CONFIG_PATH,
                                                            _canonical_unit_name(name))))


def _enabled(name):
    is_enabled = not bool(__salt__['cmd.retcode'](_systemctl_cmd('is-enabled', name)))
    return is_enabled or _templated_instance_enabled(name)


def enabled(name):
    '''
    Return if the named service is enabled to start on boot

    CLI Example::

        salt '*' service.enabled <service name>
    '''
    return _enabled(name)


def disabled(name):
    '''
    Return if the named service is disabled to start on boot

    CLI Example::

        salt '*' service.disabled <service name>
    '''
    return not _enabled(name)
