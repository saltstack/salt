# -*- coding: utf-8 -*-
'''
Provide the service module for systemd
'''
# Import python libs
import logging
import os
import re

log = logging.getLogger(__name__)

__func_alias__ = {
    'reload_': 'reload'
}

LOCAL_CONFIG_PATH = '/etc/systemd/system'
VALID_UNIT_TYPES = ['service', 'socket', 'device', 'mount', 'automount',
                    'swap', 'target', 'path', 'timer']


def __virtual__():
    '''
    Only work on systems that have been booted with systemd
    '''
    if __grains__['kernel'] == 'Linux' and _sd_booted():
        return 'service'
    return False


def _sd_booted():
    '''
    Return True if the system was booted with systemd, False otherwise.
    '''
    # We can cache this for as long as the minion runs.
    if not "systemd.sd_booted" in __context__:
        try:
            # This check does the same as sd_booted() from libsystemd-daemon:
            # http://www.freedesktop.org/software/systemd/man/sd_booted.html
            if os.stat('/run/systemd/system'):
                __context__['systemd.sd_booted'] = True
        except OSError:
            __context__['systemd.sd_booted'] = False

    return __context__['systemd.sd_booted']


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
    rexp = re.compile(r'(?m)^(?P<name>.+)\.(?P<type>' +
                      '|'.join(VALID_UNIT_TYPES) +
                      r')\s+(?P<state>.+)$')

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


def _untracked_custom_unit_found(name):
    '''
    If the passed service name is not in the output from get_all(), but a unit
    file exist in /etc/systemd/system, return True. Otherwise, return False.
    '''
    unit_path = os.path.join('/etc/systemd/system',
                             _canonical_unit_name(name))
    return (name not in get_all() and os.access(unit_path, os.R_OK))


def _unit_file_changed(name):
    '''
    Returns True if systemctl reports that the unit file has changed, otherwise
    returns False.
    '''
    return 'warning: unit file changed on disk' in \
        __salt__['cmd.run'](_systemctl_cmd('status', name)).lower()


def systemctl_reload():
    '''
    Reloads systemctl, an action needed whenever unit files are updated.

    CLI Example:

    .. code-block:: bash

        salt '*' service.systemctl_reload
    '''
    retcode = __salt__['cmd.retcode']('systemctl --system daemon-reload')
    if retcode != 0:
        log.error('Problem performing systemctl daemon-reload')
    return retcode == 0


def get_enabled():
    '''
    Return a list of all enabled services

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

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

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    return sorted(_get_all_unit_files().keys())


def available(name):
    '''
    Check that the given service is available taking into account
    template units.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available sshd
    '''
    return _canonical_template_unit_name(name) in get_all()


def start(name):
    '''
    Start the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    if _untracked_custom_unit_found(name) or _unit_file_changed(name):
        systemctl_reload()
    return not __salt__['cmd.retcode'](_systemctl_cmd('start', name))


def stop(name):
    '''
    Stop the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    if _untracked_custom_unit_found(name) or _unit_file_changed(name):
        systemctl_reload()
    return not __salt__['cmd.retcode'](_systemctl_cmd('stop', name))


def restart(name):
    '''
    Restart the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    if _untracked_custom_unit_found(name) or _unit_file_changed(name):
        systemctl_reload()
    return not __salt__['cmd.retcode'](_systemctl_cmd('restart', name))


def reload_(name):
    '''
    Reload the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    if _untracked_custom_unit_found(name) or _unit_file_changed(name):
        systemctl_reload()
    return not __salt__['cmd.retcode'](_systemctl_cmd('reload', name))


def force_reload(name):
    '''
    Force-reload the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.force_reload <service name>
    '''
    if _untracked_custom_unit_found(name) or _unit_file_changed(name):
        systemctl_reload()
    return not __salt__['cmd.retcode'](_systemctl_cmd('force-reload', name))


# The unused sig argument is required to maintain consistency in the state
# system
def status(name, sig=None):
    '''
    Return the status for a service via systemd, returns a bool
    whether the service is running.

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    '''
    if _untracked_custom_unit_found(name) or _unit_file_changed(name):
        systemctl_reload()
    cmd = 'systemctl is-active {0}'.format(_canonical_unit_name(name))
    return not __salt__['cmd.retcode'](cmd)


def enable(name, **kwargs):
    '''
    Enable the named service to start when the system boots

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    '''
    if _untracked_custom_unit_found(name) or _unit_file_changed(name):
        systemctl_reload()
    return not __salt__['cmd.retcode'](_systemctl_cmd('enable', name))


def disable(name, **kwargs):
    '''
    Disable the named service to not start when the system boots

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    if _untracked_custom_unit_found(name) or _unit_file_changed(name):
        systemctl_reload()
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
    return len(__salt__['cmd.run'](
        find_unit_by_name.format(LOCAL_CONFIG_PATH,
                                 _canonical_unit_name(name))
    ))


def _enabled(name):
    is_enabled = \
        not __salt__['cmd.retcode'](_systemctl_cmd('is-enabled', name))
    return is_enabled or _templated_instance_enabled(name)


def enabled(name):
    '''
    Return if the named service is enabled to start on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    '''
    return _enabled(name)


def disabled(name):
    '''
    Return if the named service is disabled to start on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    '''
    return not _enabled(name)
