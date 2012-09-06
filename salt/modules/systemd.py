'''
Provide the service module for systemd
'''
# Import Python libs
import re
# Import Salt libs
import salt.utils

VALID_UNIT_TYPES = ['service','socket', 'device', 'mount', 'automount',
                    'swap', 'target', 'path', 'timer']

def __virtual__():
    '''
    Only work on systems which default to systemd
    '''
    if __grains__['os'] == 'Fedora' and __grains__['osrelease'] > 15:
        return 'service'
    elif __grains__['os'] == 'openSUSE':
        return 'service'
    return False


def _systemctl_cmd(action, name):
    '''
    Build a systemctl command line. Treat unit names without one
    of the valid suffixes as a service.
    '''
    if not any(name.endswith(suffix) for suffix in VALID_UNIT_TYPES):
        name += '.service'
    return 'systemctl {0} {1}'.format(action, name)

def _get_all_unit_files():
    '''
    Get all unit files and their state. Unit files ending in .service
    are normalized so that they can be referenced without a type suffix.
    '''
    rexp = re.compile('(?m)^(?P<name>.+)\.(?P<type>' +
                      '|'.join(VALID_UNIT_TYPES) +
                      ')\s+(?P<state>.+)$')

    out = __salt__['cmd.run_stdout']('systemctl --no-legend list-unit-files | col -b')

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


# The unused sig argument is required to maintain consistency in the state
# system
def status(name, sig=None):
    '''
    Return the status for a service via systemd, returns the PID if the service
    is running or an empty string if the service is not running

    CLI Example::

        salt '*' service.status <service name>
    '''
    ret = __salt__['cmd.run'](_systemctl_cmd('show', name))
    index1 = ret.find('\nMainPID=')
    index2 = ret.find('\n', index1+9)
    mainpid = ret[index1+9:index2]
    if mainpid == '0':
        return ''
    return mainpid


def enable(name):
    '''
    Enable the named service to start when the system boots

    CLI Example::

        salt '*' service.enable <service name>
    '''
    return not __salt__['cmd.retcode'](_systemctl_cmd('enable', name))


def disable(name):
    '''
    Disable the named service to not start when the system boots

    CLI Example::

        salt '*' service.disable <service name>
    '''
    return not __salt__['cmd.retcode'](_systemctl_cmd('disable', name))


def enabled(name):
    '''
    Return if the named service is enabled to start on boot

    CLI Example::

        salt '*' service.enabled <service name>
    '''
    return not __salt__['cmd.retcode'](_systemctl_cmd('is-enabled', name))


def disabled(name):
    '''
    Return if the named service is disabled to start on boot

    CLI Example::

        salt '*' service.disabled <service name>
    '''
    return bool(__salt__['cmd.retcode'](_systemctl_cmd('is-enabled', name)))
