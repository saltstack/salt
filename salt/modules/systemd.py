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
LEGACY_INIT_SCRIPT_PATH = '/etc/init.d'
VALID_UNIT_TYPES = ['service', 'socket', 'device', 'mount', 'automount',
                    'swap', 'target', 'path', 'timer']

# Define the module's virtual name
__virtualname__ = 'service'


def __virtual__():
    '''
    Only work on systems that have been booted with systemd
    '''
    if __grains__['kernel'] == 'Linux' and _sd_booted(__context__):
        return __virtualname__
    return False


def _sd_booted(context):
    '''
    Return True if the system was booted with systemd, False otherwise.
    '''
    # We can cache this for as long as the minion runs.
    if "systemd.sd_booted" not in context:
        try:
            # This check does the same as sd_booted() from libsystemd-daemon:
            # http://www.freedesktop.org/software/systemd/man/sd_booted.html
            if os.stat('/run/systemd/system'):
                context['systemd.sd_booted'] = True
        except OSError:
            context['systemd.sd_booted'] = False

    return context['systemd.sd_booted']


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


def _get_all_units():
    '''
    Get all units and their state. Units ending in .service
    are normalized so that they can be referenced without a type suffix.
    '''
    rexp = re.compile(r'(?m)^(?P<name>.+)\.(?P<type>' +
                      '|'.join(VALID_UNIT_TYPES) +
                      r')\s+loaded\s+(?P<active>[^\s]+)')

    out = __salt__['cmd.run_stdout'](
        'systemctl --all --full --no-legend --no-pager list-units | col -b',
        python_shell=True
    )

    ret = {}
    for match in rexp.finditer(out):
        name = match.group('name')
        if match.group('type') != 'service':
            name += '.' + match.group('type')
        ret[name] = match.group('active')
    return ret


def _get_all_unit_files():
    '''
    Get all unit files and their state. Unit files ending in .service
    are normalized so that they can be referenced without a type suffix.
    '''
    rexp = re.compile(r'(?m)^(?P<name>.+)\.(?P<type>' +
                      '|'.join(VALID_UNIT_TYPES) +
                      r')\s+(?P<state>.+)$')

    out = __salt__['cmd.run_stdout'](
        'systemctl --full --no-legend --no-pager list-unit-files | col -b',
        python_shell=True
    )

    ret = {}
    for match in rexp.finditer(out):
        name = match.group('name')
        if match.group('type') != 'service':
            name += '.' + match.group('type')
        ret[name] = match.group('state')
    return ret


def _get_all_legacy_init_scripts():
    '''
    Get all old-fashioned init-style scripts. State is always inactive, because systemd would already show them
    otherwise.
    '''
    ret = {}
    if not os.path.isdir(LEGACY_INIT_SCRIPT_PATH):
        return ret
    for fn in os.listdir(LEGACY_INIT_SCRIPT_PATH):
        if not os.path.isfile(os.path.join(LEGACY_INIT_SCRIPT_PATH, fn)) or fn.startswith('rc'):
            continue
        log.info('Legacy init script: "%s".', fn)
        ret[fn] = 'inactive'
    return ret


def _untracked_custom_unit_found(name):
    '''
    If the passed service name is not in the output from get_all(), but a unit
    file exist in /etc/systemd/system, return True. Otherwise, return False.
    '''
    unit_path = os.path.join('/etc/systemd/system',
                             _canonical_unit_name(name))
    return name not in get_all() and os.access(unit_path, os.R_OK)


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
    for name, state in _get_all_unit_files().iteritems() + _get_all_legacy_init_scripts().iteritems():
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
    return sorted(set(list(_get_all_units().keys()) + list(_get_all_unit_files().keys())
                      + list(_get_all_legacy_init_scripts().keys())))


def available(name):
    '''
    Check that the given service is available taking into account
    template units.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available sshd
    '''
    name = _canonical_template_unit_name(name)
    units = get_all()
    if name in units:
        return True
    elif '@' in name:
        templatename = name[:name.find('@') + 1]
        return templatename in units
    else:
        return False


def missing(name):
    '''
    The inverse of service.available.
    Returns ``True`` if the specified service is not available, otherwise returns
    ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing sshd
    '''
    return not available(name)


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
    return not __salt__['cmd.retcode'](_systemctl_cmd('is-active', name))


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
        not __salt__['cmd.retcode'](_systemctl_cmd('is-enabled', name),
                                    ignore_retcode=True)
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


def show(name):
    '''
    Show properties of one or more units/jobs or the manager

    CLI Example:

        salt '*' service.show <service name>
    '''
    ret = {}
    for line in __salt__['cmd.run'](_systemctl_cmd('show', name)).splitlines():
        comps = line.split('=')
        name = comps[0]
        value = '='.join(comps[1:])
        if value.startswith('{'):
            value = value.replace('{', '').replace('}', '')
            ret[name] = {}
            for item in value.split(' ; '):
                comps = item.split('=')
                ret[name][comps[0].strip()] = comps[1].strip()
        elif name in ('Before', 'After', 'Wants'):
            ret[name] = value.split()
        else:
            ret[name] = value

    return ret


def execs():
    '''
    Return a list of all files specified as ``ExecStart`` for all services.

    CLI Example:

        salt '*' service.execs
    '''
    execs_ = {}
    for service in get_all():
        data = show(service)
        if 'ExecStart' not in data:
            continue
        execs_[service] = data['ExecStart']['path']

    return execs_
