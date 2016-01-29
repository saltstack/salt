# -*- coding: utf-8 -*-
'''
Provide the service module for systemd
'''
# Import python libs
from __future__ import absolute_import
import glob
import logging
import os
import re
import shlex

# Import 3rd-party libs
import salt.ext.six as six
import salt.utils.itertools
import salt.utils.systemd
from salt.exceptions import CommandExecutionError, CommandNotFoundError

log = logging.getLogger(__name__)

__func_alias__ = {
    'reload_': 'reload'
}

LOCAL_CONFIG_PATH = '/etc/systemd/system'
LEGACY_INIT_SCRIPT_PATH = '/etc/init.d'
VALID_UNIT_TYPES = ('service', 'socket', 'device', 'mount', 'automount',
                    'swap', 'target', 'path', 'timer')

# Define the module's virtual name
__virtualname__ = 'service'


def __virtual__():
    '''
    Only work on systems that have been booted with systemd
    '''
    if __grains__['kernel'] == 'Linux' \
            and salt.utils.systemd.booted(__context__):
        return __virtualname__
    return (
        False,
        'The systemd execution module failed to load: only available on Linux '
        'systems which have been booted with systemd.'
    )


def _canonical_unit_name(name):
    '''
    Build a canonical unit name treating unit names without one
    of the valid suffixes as a service.
    '''
    if not isinstance(name, six.string_types):
        name = str(name)
    if any(name.endswith(suffix) for suffix in VALID_UNIT_TYPES):
        return name
    return '{0}.service'.format(name)


def _systemctl_cmd(action, name=None):
    '''
    Build a systemctl command line. Treat unit names without one
    of the valid suffixes as a service.
    '''
    ret = ['systemctl']
    ret.extend(shlex.split(action))
    if name:
        ret.append(_canonical_unit_name(name))
    if 'status' in ret:
        ret.extend(['-n', '0'])
    return ret


def _get_all_units():
    '''
    Get all units and their state. Units ending in .service
    are normalized so that they can be referenced without a type suffix.
    '''
    rexp = re.compile(r'(?m)^(?P<name>.+)\.(?P<type>' +
                      '|'.join(VALID_UNIT_TYPES) +
                      r')\s+loaded\s+(?P<active>[^\s]+)')

    out = __salt__['cmd.run_stdout'](
        _systemctl_cmd('--all --full --no-legend --no-pager list-units'),
        python_shell=False
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
        _systemctl_cmd(
            'systemctl --full --no-legend --no-pager list-unit-files'
        ),
        python_shell=False
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
    Get all old-fashioned init-style scripts. State is always inactive, because
    systemd would already show them otherwise.
    '''
    ret = {}
    if not os.path.isdir(LEGACY_INIT_SCRIPT_PATH):
        return ret
    for initscript_name in os.listdir(LEGACY_INIT_SCRIPT_PATH):
        if initscript_name.startswith('rc'):
            continue
        full_path = os.path.join(LEGACY_INIT_SCRIPT_PATH, initscript_name)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            log.info('Legacy init script: \'%s\'.', initscript_name)
            ret[initscript_name] = 'inactive'
    return ret


def _untracked_custom_unit_found(name):
    '''
    If the passed service name is not available, but a unit file exist in
    /etc/systemd/system, return True. Otherwise, return False.
    '''
    unit_path = os.path.join('/etc/systemd/system',
                             _canonical_unit_name(name))
    return os.access(unit_path, os.R_OK) and not available(name)


def _unit_file_changed(name):
    '''
    Returns True if systemctl reports that the unit file has changed, otherwise
    returns False.
    '''
    out = __salt__['cmd.run'](_systemctl_cmd('status', name),
                              python_shell=False,
                              ignore_retcode=True).lower()
    return "'systemctl daemon-reload'" in out


def systemctl_reload():
    '''
    Reloads systemctl, an action needed whenever unit files are updated.

    CLI Example:

    .. code-block:: bash

        salt '*' service.systemctl_reload
    '''
    out = __salt__['cmd.run_all'](
        _systemctl_cmd('--system daemon-reload'),
        python_shell=False,
        redirect_stderr=True
    )
    if out['retcode'] != 0:
        raise CommandExecutionError(
            'Problem performing systemctl daemon-reload',
            info=out['stdout']
        )
    return True


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
    if 'systemd._runlevel' in __context__:
        return __context__['systemd._runlevel']
    out = __salt__['cmd.run']('runlevel', python_shell=False)
    try:
        ret = out.split()[1]
    except IndexError:
        # The runlevel is unknown, return the default
        ret = _default_runlevel()
    __context__['systemd._runlevel'] = ret
    return ret


def _get_service_exec():
    '''
    Debian uses update-rc.d to manage System-V style services.
    http://www.debian.org/doc/debian-policy/ch-opersys.html#s9.3.3
    '''
    executable = 'update-rc.d'
    salt.utils.check_or_die(executable)
    return executable


def _check_for_unit_changes(name):
    '''
    Check for modified/updated unit files, and run a daemon-reload if any are
    found.
    '''
    contextkey = 'systemd._check_for_unit_changes'
    if contextkey not in __context__:
        if _untracked_custom_unit_found(name) or _unit_file_changed(name):
            systemctl_reload()
        # Set context key to avoid repeating this check
        __context__[contextkey] = True


def _has_sysv_exec():
    '''
    Return the current runlevel
    '''
    if 'systemd._has_sysv_exec' not in __context__:
        try:
            __context__['systemd._has_sysv_exec'] = bool(_get_service_exec())
        except (CommandExecutionError, CommandNotFoundError):
            __context__['systemd._has_sysv_exec'] = False
    return __context__['systemd._has_sysv_exec']


def _sysv_exists(name):
    script = '/etc/init.d/{0}'.format(name)
    return os.access(script, os.X_OK)


def _service_is_sysv(name):
    '''
    A System-V style service will have a control script in
    /etc/init.d.
    Return True only if the service doesnt also provide a systemd unit file.
    '''
    return (_has_sysv_exec() and
            name in _get_all_units() and
            name not in _get_all_unit_files() and
            _sysv_exists(name))


def _sysv_is_enabled(name):
    '''
    A System-V style service is assumed disabled if the "startup" symlink
    (starts with "S") to its script is found in /etc/init.d in the current
    runlevel.
    '''
    return bool(glob.glob('/etc/rc{0}.d/S*{1}'.format(_runlevel(), name)))


def get_enabled():
    '''
    Return a list of all enabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    ret = []
    units = _get_all_unit_files()
    services = _get_all_units()
    for name, state in six.iteritems(units):
        if state.strip() == 'enabled':
            ret.append(name)
    for name, state in six.iteritems(services):
        if name in units:
            continue
        # performance; if the legacy initscript doesnt exists,
        # don't contiue up with systemd query
        if not _service_is_sysv(name):
            continue
        if _sysv_is_enabled(name):
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
    known_services = _get_all_unit_files()
    known_services.update(_get_all_legacy_init_scripts())
    for name, state in six.iteritems(known_services):
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
    ret = set(_get_all_units())
    ret.update(_get_all_unit_files())
    ret.update(_get_all_legacy_init_scripts())
    return sorted(ret)


def available(name):
    '''
    Check that the given service is available taking into account
    template units.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available sshd
    '''
    out = __salt__['cmd.run'](_systemctl_cmd('status', name),
                              python_shell=False,
                              ignore_retcode=True)
    for line in salt.utils.itertools.split(out.lower(), '\n'):
        match = re.match(r'\s+loaded:\s+(\S+)', line)
        if match:
            ret = match.group(1) != 'not-found'
            break
    else:
        raise CommandExecutionError(
            'Failed to get information on service unit \'{0}\''.format(name),
            info=out
        )
    return ret


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


def unmask(name):
    '''
    Unmask the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.unmask <service name>
    '''
    _check_for_unit_changes(name)
    mask_status = masked(name)
    if not mask_status:
        log.debug('Service \'{0}\' is not masked'.format(name))
        return True

    cmd = 'unmask --runtime' if 'runtime' in mask_status else 'unmask'
    out = __salt__['cmd.run_all'](_systemctl_cmd(cmd, name),
                                  python_shell=False,
                                  redirect_stderr=True)

    if out['retcode'] != 0:
        raise CommandExecutionError(
            'Failed to unmask service \'{0}\''.format(name),
            info=out['stdout']
        )

    return True


def mask(name, runtime=False):
    '''
    Mask the specified service with systemd

    runtime : False
        Set to ``True`` to mask this service only until the next reboot

        .. versionadded:: Boron

    CLI Example:

    .. code-block:: bash

        salt '*' service.mask <service name>
    '''
    _check_for_unit_changes(name)

    cmd = 'mask --runtime' if runtime else 'mask'
    out = __salt__['cmd.run_all'](_systemctl_cmd(cmd, name),
                                  python_shell=False,
                                  redirect_stderr=True)

    if out['retcode'] != 0:
        raise CommandExecutionError(
            'Failed to mask service \'{0}\''.format(name),
            info=out['stdout']
        )

    return True


def masked(name):
    '''
    .. versionadded:: 2015.8.0
    .. versionchanged:: Boron
        The return data for this function has changed. If the service is
        masked, the return value will now be the output of the ``systemctl
        is-enabled`` command (so that a persistent mask can be distinguished
        from a runtime mask). If the service is not masked, then ``False`` will
        be returned.

    Check whether or not a service is masked

    CLI Example:

    .. code-block:: bash

        salt '*' service.masked <service name>
    '''
    _check_for_unit_changes(name)
    out = __salt__['cmd.run'](
        _systemctl_cmd('is-enabled', name),
        python_shell=False,
        ignore_retcode=True,
    )
    return out if 'masked' in out else False


def start(name):
    '''
    Start the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    _check_for_unit_changes(name)
    unmask(name)
    return __salt__['cmd.retcode'](_systemctl_cmd('start', name),
                                   python_shell=False) == 0


def stop(name):
    '''
    Stop the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    _check_for_unit_changes(name)
    return __salt__['cmd.retcode'](_systemctl_cmd('stop', name),
                                   python_shell=False) == 0


def restart(name):
    '''
    Restart the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    _check_for_unit_changes(name)
    unmask(name)
    return __salt__['cmd.retcode'](_systemctl_cmd('restart', name),
                                   python_shell=False) == 0


def reload_(name):
    '''
    Reload the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    _check_for_unit_changes(name)
    unmask(name)
    return __salt__['cmd.retcode'](_systemctl_cmd('reload', name),
                                   python_shell=False) == 0


def force_reload(name):
    '''
    Force-reload the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.force_reload <service name>
    '''
    _check_for_unit_changes(name)
    unmask(name)
    return __salt__['cmd.retcode'](_systemctl_cmd('force-reload', name),
                                   python_shell=False) == 0


# The sig argument is required to maintain consistency with service states. It
# is unused in this function.
def status(name, sig=None):
    '''
    Return the status for a service via systemd, returns ``True`` if the
    service is running and ``False`` if it is not.

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    '''
    _check_for_unit_changes(name)
    return __salt__['cmd.retcode'](_systemctl_cmd('is-active', name),
                                   python_shell=False,
                                   ignore_retcode=True) == 0


def enable(name, **kwargs):
    '''
    Enable the named service to start when the system boots

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    '''
    _check_for_unit_changes(name)
    unmask(name)
    if _service_is_sysv(name):
        cmd = [_get_service_exec(), '-f', name, 'defaults', '99']
        return __salt__['cmd.retcode'](cmd,
                                       python_shell=False,
                                       ignore_retcode=True) == 0
    return __salt__['cmd.retcode'](_systemctl_cmd('enable', name),
                                   python_shell=False,
                                   ignore_retcode=True) == 0


def disable(name, **kwargs):
    '''
    Disable the named service to not start when the system boots

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    _check_for_unit_changes(name)
    if _service_is_sysv(name):
        cmd = [_get_service_exec(), '-f', name, 'remove']
        return __salt__['cmd.retcode'](cmd,
                                       python_shell=False,
                                       ignore_retcode=True) == 0
    return __salt__['cmd.retcode'](_systemctl_cmd('disable', name),
                                   python_shell=False,
                                   ignore_retcode=True) == 0


def _enabled(name):
    '''
    Try ``systemctl is-enabled`` first, then look for a symlink created by
    systemctl (older systemd releases did not support using is-enabled to check
    templated services), and lastly check for a sysvinit service.
    '''
    if __salt__['cmd.retcode'](_systemctl_cmd('is-enabled', name),
                               python_shell=False,
                               ignore_retcode=True) == 0:
        return True
    elif '@' in name:
        # On older systemd releases, templated services could not be checked
        # with ``systemctl is-enabled``. As a fallback, look for the symlinks
        # created by systemctl when enabling templated services.
        cmd = ['find', LOCAL_CONFIG_PATH, '-name', name,
               '-type', 'l', '-print', '-quit']
        # If the find command returns any matches, there will be output and the
        # string will be non-empty.
        if bool(__salt__['cmd.run'](cmd, python_shell=False)):
            return True
    else:
        return _sysv_is_enabled(name)


def enabled(name, **kwargs):
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
    out = __salt__['cmd.run'](_systemctl_cmd('show', name),
                              python_shell=False)
    for line in salt.utils.itertools.split(out, '\n'):
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
    ret = {}
    for service in get_all():
        data = show(service)
        if 'ExecStart' not in data:
            continue
        ret[service] = data['ExecStart']['path']
    return ret
