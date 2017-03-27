# -*- coding: utf-8 -*-
'''
Provides the service module for systemd

.. versionadded:: 0.10.0

.. important::
    If you feel that Salt should be using this module to manage services on a
    minion, and it is using a different module (or gives an error similar to
    *'service.start' is not available*), see :ref:`here
    <module-provider-override>`.
'''
# Import python libs
from __future__ import absolute_import
import errno
import glob
import logging
import os
import re
import shlex

# Import 3rd-party libs
import salt.utils.itertools
import salt.utils.systemd
from salt.exceptions import CommandExecutionError
from salt.ext import six

log = logging.getLogger(__name__)

__func_alias__ = {
    'reload_': 'reload'
}

SYSTEM_CONFIG_PATHS = ('/lib/systemd/system', '/usr/lib/systemd/system')
LOCAL_CONFIG_PATH = '/etc/systemd/system'
INITSCRIPT_PATH = '/etc/init.d'
VALID_UNIT_TYPES = ('service', 'socket', 'device', 'mount', 'automount',
                    'swap', 'target', 'path', 'timer')

# Define the module's virtual name
__virtualname__ = 'service'

# Disable check for string substitution
# pylint: disable=E1321


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
    return '%s.service' % name


def _check_available(name):
    '''
    Returns boolean telling whether or not the named service is available
    '''
    _status = _systemctl_status(name)
    sd_version = salt.utils.systemd.version(__context__)
    if sd_version is not None and sd_version >= 231:
        # systemd 231 changed the output of "systemctl status" for unknown
        # services, and also made it return an exit status of 4. If we are on
        # a new enough version, check the retcode, otherwise fall back to
        # parsing the "systemctl status" output.
        # See: https://github.com/systemd/systemd/pull/3385
        # Also: https://github.com/systemd/systemd/commit/3dced37
        return 0 <= _status['retcode'] < 4

    out = _status['stdout'].lower()
    if 'could not be found' in out:
        # Catch cases where the systemd version is < 231 but the return code
        # and output changes have been backported (e.g. RHEL 7.3).
        return False

    for line in salt.utils.itertools.split(out, '\n'):
        match = re.match(r'\s+loaded:\s+(\S+)', line)
        if match:
            ret = match.group(1) != 'not-found'
            break
    else:
        raise CommandExecutionError(
            'Failed to get information on unit \'%s\'' % name
        )
    return ret


def _check_for_unit_changes(name):
    '''
    Check for modified/updated unit files, and run a daemon-reload if any are
    found.
    '''
    contextkey = 'systemd._check_for_unit_changes.{0}'.format(name)
    if contextkey not in __context__:
        if _untracked_custom_unit_found(name) or _unit_file_changed(name):
            systemctl_reload()
        # Set context key to avoid repeating this check
        __context__[contextkey] = True


def _clear_context():
    '''
    Remove context
    '''
    # Using list() here because modifying a dictionary during iteration will
    # raise a RuntimeError.
    for key in list(__context__):
        try:
            if key.startswith('systemd._systemctl_status.'):
                __context__.pop(key)
        except AttributeError:
            continue


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


def _get_systemd_services():
    '''
    Use os.listdir() to get all the unit files
    '''
    ret = set()
    for path in SYSTEM_CONFIG_PATHS + (LOCAL_CONFIG_PATH,):
        # Make sure user has access to the path, and if the path is a link
        # it's likely that another entry in SYSTEM_CONFIG_PATHS or LOCAL_CONFIG_PATH
        # points to it, so we can ignore it.
        if os.access(path, os.R_OK) and not os.path.islink(path):
            for fullname in os.listdir(path):
                try:
                    unit_name, unit_type = fullname.rsplit('.', 1)
                except ValueError:
                    continue
                if unit_type in VALID_UNIT_TYPES:
                    ret.add(unit_name if unit_type == 'service' else fullname)
    return ret


def _get_sysv_services(systemd_services=None):
    '''
    Use os.listdir() and os.access() to get all the initscripts
    '''
    try:
        sysv_services = os.listdir(INITSCRIPT_PATH)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            pass
        elif exc.errno == errno.EACCES:
            log.error(
                'Unable to check sysvinit scripts, permission denied to %s',
                INITSCRIPT_PATH
            )
        else:
            log.error(
                'Error %d encountered trying to check sysvinit scripts: %s',
                exc.errno,
                exc.strerror
            )
        return []

    if systemd_services is None:
        systemd_services = _get_systemd_services()

    ret = []
    for sysv_service in sysv_services:
        if os.access(os.path.join(INITSCRIPT_PATH, sysv_service), os.X_OK):
            if sysv_service in systemd_services:
                log.debug(
                    'sysvinit script \'%s\' found, but systemd unit '
                    '\'%s.service\' already exists',
                    sysv_service, sysv_service
                )
                continue
            ret.append(sysv_service)
    return ret


def _get_service_exec():
    '''
    Returns the path to the sysv service manager (either update-rc.d or
    chkconfig)
    '''
    contextkey = 'systemd._get_service_exec'
    if contextkey not in __context__:
        executables = ('update-rc.d', 'chkconfig')
        for executable in executables:
            service_exec = salt.utils.which(executable)
            if service_exec is not None:
                break
        else:
            raise CommandExecutionError(
                'Unable to find sysv service manager (tried {0})'.format(
                    ', '.join(executables)
                )
            )
        __context__[contextkey] = service_exec
    return __context__[contextkey]


def _runlevel():
    '''
    Return the current runlevel
    '''
    contextkey = 'systemd._runlevel'
    if contextkey in __context__:
        return __context__[contextkey]
    out = __salt__['cmd.run']('runlevel', python_shell=False)
    try:
        ret = out.split()[1]
    except IndexError:
        # The runlevel is unknown, return the default
        ret = _default_runlevel()
    __context__[contextkey] = ret
    return ret


def _systemctl_cmd(action, name=None, systemd_scope=False):
    '''
    Build a systemctl command line. Treat unit names without one
    of the valid suffixes as a service.
    '''
    ret = []
    if systemd_scope \
            and salt.utils.systemd.has_scope(__context__) \
            and __salt__['config.get']('systemd.scope', True):
        ret.extend(['systemd-run', '--scope'])
    ret.append('systemctl')
    if isinstance(action, six.string_types):
        action = shlex.split(action)
    ret.extend(action)
    if name is not None:
        ret.append(_canonical_unit_name(name))
    if 'status' in ret:
        ret.extend(['-n', '0'])
    return ret


def _systemctl_status(name):
    '''
    Helper function which leverages __context__ to keep from running 'systemctl
    status' more than once.
    '''
    contextkey = 'systemd._systemctl_status.%s' % name
    if contextkey in __context__:
        return __context__[contextkey]
    __context__[contextkey] = __salt__['cmd.run_all'](
        _systemctl_cmd('status', name),
        python_shell=False,
        redirect_stderr=True,
        ignore_retcode=True
    )
    return __context__[contextkey]


def _sysv_enabled(name):
    '''
    A System-V style service is assumed disabled if the "startup" symlink
    (starts with "S") to its script is found in /etc/init.d in the current
    runlevel.
    '''
    # Find exact match (disambiguate matches like "S01anacron" for cron)
    for match in glob.glob('/etc/rc%s.d/S*%s' % (_runlevel(), name)):
        if re.match(r'S\d{,2}%s' % name, os.path.basename(match)):
            return True
    return False


def _untracked_custom_unit_found(name):
    '''
    If the passed service name is not available, but a unit file exist in
    /etc/systemd/system, return True. Otherwise, return False.
    '''
    unit_path = os.path.join('/etc/systemd/system',
                             _canonical_unit_name(name))
    return os.access(unit_path, os.R_OK) and not _check_available(name)


def _unit_file_changed(name):
    '''
    Returns True if systemctl reports that the unit file has changed, otherwise
    returns False.
    '''
    return "'systemctl daemon-reload'" in _systemctl_status(name)['stdout'].lower()


def systemctl_reload():
    '''
    .. versionadded:: 0.15.0

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
            'Problem performing systemctl daemon-reload: %s' % out['stdout']
        )
    _clear_context()
    return True


def get_enabled():
    '''
    Return a list of all enabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    '''
    ret = set()
    # Get enabled systemd units. Can't use --state=enabled here because it's
    # not present until systemd 216.
    out = __salt__['cmd.run'](
        _systemctl_cmd('--full --no-legend --no-pager list-unit-files'),
        python_shell=False,
        ignore_retcode=True,
    )
    for line in salt.utils.itertools.split(out, '\n'):
        try:
            fullname, unit_state = line.strip().split(None, 1)
        except ValueError:
            continue
        else:
            if unit_state != 'enabled':
                continue
        try:
            unit_name, unit_type = fullname.rsplit('.', 1)
        except ValueError:
            continue
        if unit_type in VALID_UNIT_TYPES:
            ret.add(unit_name if unit_type == 'service' else fullname)

    # Add in any sysvinit services that are enabled
    ret.update(set(
        [x for x in _get_sysv_services() if _sysv_enabled(x)]
    ))
    return sorted(ret)


def get_disabled():
    '''
    Return a list of all disabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    '''
    ret = set()
    # Get disabled systemd units. Can't use --state=disabled here because it's
    # not present until systemd 216.
    out = __salt__['cmd.run'](
        _systemctl_cmd('--full --no-legend --no-pager list-unit-files'),
        python_shell=False,
        ignore_retcode=True,
    )
    for line in salt.utils.itertools.split(out, '\n'):
        try:
            fullname, unit_state = line.strip().split(None, 1)
        except ValueError:
            continue
        else:
            if unit_state != 'disabled':
                continue
        try:
            unit_name, unit_type = fullname.rsplit('.', 1)
        except ValueError:
            continue
        if unit_type in VALID_UNIT_TYPES:
            ret.add(unit_name if unit_type == 'service' else fullname)

    # Add in any sysvinit services that are disabled
    ret.update(set(
        [x for x in _get_sysv_services() if not _sysv_enabled(x)]
    ))
    return sorted(ret)


def get_static():
    '''
    .. versionadded:: 2015.8.5

    Return a list of all static services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_static
    '''
    ret = set()
    # Get static systemd units. Can't use --state=static here because it's
    # not present until systemd 216.
    out = __salt__['cmd.run'](
        _systemctl_cmd('--full --no-legend --no-pager list-unit-files'),
        python_shell=False,
        ignore_retcode=True,
    )
    for line in salt.utils.itertools.split(out, '\n'):
        try:
            fullname, unit_state = line.strip().split(None, 1)
        except ValueError:
            continue
        else:
            if unit_state != 'static':
                continue
        try:
            unit_name, unit_type = fullname.rsplit('.', 1)
        except ValueError:
            continue
        if unit_type in VALID_UNIT_TYPES:
            ret.add(unit_name if unit_type == 'service' else fullname)

    # sysvinit services cannot be static
    return sorted(ret)


def get_all():
    '''
    Return a list of all available services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    '''
    ret = _get_systemd_services()
    ret.update(set(_get_sysv_services(systemd_services=ret)))
    return sorted(ret)


def available(name):
    '''
    .. versionadded:: 0.10.4

    Check that the given service is available taking into account template
    units.

    CLI Example:

    .. code-block:: bash

        salt '*' service.available sshd
    '''
    _check_for_unit_changes(name)
    return _check_available(name)


def missing(name):
    '''
    .. versionadded:: 2014.1.0

    The inverse of :py:func:`service.available
    <salt.modules.systemd.available>`. Returns ``True`` if the specified
    service is not available, otherwise returns ``False``.

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing sshd
    '''
    return not available(name)


def unmask(name):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands run by this function from the ``salt-minion`` daemon's
        control group. This is done to avoid a race condition in cases where
        the ``salt-minion`` service is restarted while a service is being
        modified. If desired, usage of `systemd-run(1)`_ can be suppressed by
        setting a :mod:`config option <salt.modules.config.get>` called
        ``systemd.scope``, with a value of ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html

    Unmask the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.unmask <service name>
    '''
    _check_for_unit_changes(name)
    mask_status = masked(name)
    if not mask_status:
        log.debug('Service \'%s\' is not masked', name)
        return True

    cmd = 'unmask --runtime' if 'runtime' in mask_status else 'unmask'
    out = __salt__['cmd.run_all'](_systemctl_cmd(cmd, name, systemd_scope=True),
                                  python_shell=False,
                                  redirect_stderr=True)

    if out['retcode'] != 0:
        raise CommandExecutionError('Failed to unmask service \'%s\'' % name)

    return True


def mask(name, runtime=False):
    '''
    .. versionadded:: 2015.5.0
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands run by this function from the ``salt-minion`` daemon's
        control group. This is done to avoid a race condition in cases where
        the ``salt-minion`` service is restarted while a service is being
        modified. If desired, usage of `systemd-run(1)`_ can be suppressed by
        setting a :mod:`config option <salt.modules.config.get>` called
        ``systemd.scope``, with a value of ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html

    Mask the specified service with systemd

    runtime : False
        Set to ``True`` to mask this service only until the next reboot

        .. versionadded:: 2015.8.5

    CLI Example:

    .. code-block:: bash

        salt '*' service.mask <service name>
    '''
    _check_for_unit_changes(name)

    cmd = 'mask --runtime' if runtime else 'mask'
    out = __salt__['cmd.run_all'](_systemctl_cmd(cmd, name, systemd_scope=True),
                                  python_shell=False,
                                  redirect_stderr=True)

    if out['retcode'] != 0:
        raise CommandExecutionError(
            'Failed to mask service \'%s\'' % name,
            info=out['stdout']
        )

    return True


def masked(name):
    '''
    .. versionadded:: 2015.8.0
    .. versionchanged:: 2015.8.5
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
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands run by this function from the ``salt-minion`` daemon's
        control group. This is done to avoid a race condition in cases where
        the ``salt-minion`` service is restarted while a service is being
        modified. If desired, usage of `systemd-run(1)`_ can be suppressed by
        setting a :mod:`config option <salt.modules.config.get>` called
        ``systemd.scope``, with a value of ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html

    Start the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    '''
    _check_for_unit_changes(name)
    unmask(name)
    return __salt__['cmd.retcode'](
        _systemctl_cmd('start', name, systemd_scope=True),
        python_shell=False) == 0


def stop(name):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands run by this function from the ``salt-minion`` daemon's
        control group. This is done to avoid a race condition in cases where
        the ``salt-minion`` service is restarted while a service is being
        modified. If desired, usage of `systemd-run(1)`_ can be suppressed by
        setting a :mod:`config option <salt.modules.config.get>` called
        ``systemd.scope``, with a value of ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html

    Stop the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    '''
    _check_for_unit_changes(name)
    return __salt__['cmd.retcode'](
        _systemctl_cmd('stop', name, systemd_scope=True),
        python_shell=False) == 0


def restart(name):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands run by this function from the ``salt-minion`` daemon's
        control group. This is done to avoid a race condition in cases where
        the ``salt-minion`` service is restarted while a service is being
        modified. If desired, usage of `systemd-run(1)`_ can be suppressed by
        setting a :mod:`config option <salt.modules.config.get>` called
        ``systemd.scope``, with a value of ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html

    Restart the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    '''
    _check_for_unit_changes(name)
    unmask(name)
    return __salt__['cmd.retcode'](
        _systemctl_cmd('restart', name, systemd_scope=True),
        python_shell=False) == 0


def reload_(name):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands run by this function from the ``salt-minion`` daemon's
        control group. This is done to avoid a race condition in cases where
        the ``salt-minion`` service is restarted while a service is being
        modified. If desired, usage of `systemd-run(1)`_ can be suppressed by
        setting a :mod:`config option <salt.modules.config.get>` called
        ``systemd.scope``, with a value of ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html

    Reload the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.reload <service name>
    '''
    _check_for_unit_changes(name)
    unmask(name)
    return __salt__['cmd.retcode'](
        _systemctl_cmd('reload', name, systemd_scope=True),
        python_shell=False) == 0


def force_reload(name):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands run by this function from the ``salt-minion`` daemon's
        control group. This is done to avoid a race condition in cases where
        the ``salt-minion`` service is restarted while a service is being
        modified. If desired, usage of `systemd-run(1)`_ can be suppressed by
        setting a :mod:`config option <salt.modules.config.get>` called
        ``systemd.scope``, with a value of ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html

    .. versionadded:: 0.12.0

    Force-reload the specified service with systemd

    CLI Example:

    .. code-block:: bash

        salt '*' service.force_reload <service name>
    '''
    _check_for_unit_changes(name)
    unmask(name)
    return __salt__['cmd.retcode'](
        _systemctl_cmd('force-reload', name, systemd_scope=True),
        python_shell=False) == 0


# The unused sig argument is required to maintain consistency with the API
# established by Salt's service management states.
def status(name, sig=None):  # pylint: disable=unused-argument
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


# The unused kwargs argument is required to maintain consistency with the API
# established by Salt's service management states.
def enable(name, **kwargs):  # pylint: disable=unused-argument
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands run by this function from the ``salt-minion`` daemon's
        control group. This is done to avoid a race condition in cases where
        the ``salt-minion`` service is restarted while a service is being
        modified. If desired, usage of `systemd-run(1)`_ can be suppressed by
        setting a :mod:`config option <salt.modules.config.get>` called
        ``systemd.scope``, with a value of ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html

    Enable the named service to start when the system boots

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    '''
    _check_for_unit_changes(name)
    unmask(name)
    if name in _get_sysv_services():
        cmd = []
        if salt.utils.systemd.has_scope(__context__) \
                and __salt__['config.get']('systemd.scope', True):
            cmd.extend(['systemd-run', '--scope'])
        service_exec = _get_service_exec()
        if service_exec.endswith('/update-rc.d'):
            cmd.extend([service_exec, '-f', name, 'defaults', '99'])
        elif service_exec.endswith('/chkconfig'):
            cmd.extend([service_exec, name, 'on'])
        return __salt__['cmd.retcode'](cmd,
                                       python_shell=False,
                                       ignore_retcode=True) == 0
    return __salt__['cmd.retcode'](
        _systemctl_cmd('enable', name, systemd_scope=True),
        python_shell=False,
        ignore_retcode=True) == 0


# The unused kwargs argument is required to maintain consistency with the API
# established by Salt's service management states.
def disable(name, **kwargs):  # pylint: disable=unused-argument
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands run by this function from the ``salt-minion`` daemon's
        control group. This is done to avoid a race condition in cases where
        the ``salt-minion`` service is restarted while a service is being
        modified. If desired, usage of `systemd-run(1)`_ can be suppressed by
        setting a :mod:`config option <salt.modules.config.get>` called
        ``systemd.scope``, with a value of ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html

    Disable the named service to not start when the system boots

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    '''
    _check_for_unit_changes(name)
    if name in _get_sysv_services():
        cmd = []
        if salt.utils.systemd.has_scope(__context__) \
                and __salt__['config.get']('systemd.scope', True):
            cmd.extend(['systemd-run', '--scope'])
        service_exec = _get_service_exec()
        if service_exec.endswith('/update-rc.d'):
            cmd.extend([service_exec, '-f', name, 'remove'])
        elif service_exec.endswith('/chkconfig'):
            cmd.extend([service_exec, name, 'off'])
        return __salt__['cmd.retcode'](cmd,
                                       python_shell=False,
                                       ignore_retcode=True) == 0
    return __salt__['cmd.retcode'](
        _systemctl_cmd('disable', name, systemd_scope=True),
        python_shell=False,
        ignore_retcode=True) == 0


# The unused kwargs argument is required to maintain consistency with the API
# established by Salt's service management states.
def enabled(name, **kwargs):  # pylint: disable=unused-argument
    '''
    Return if the named service is enabled to start on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    '''
    # Try 'systemctl is-enabled' first, then look for a symlink created by
    # systemctl (older systemd releases did not support using is-enabled to
    # check templated services), and lastly check for a sysvinit service.
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
    elif name in _get_sysv_services():
        return _sysv_enabled(name)

    return False


def disabled(name):
    '''
    Return if the named service is disabled from starting on boot

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    '''
    return not enabled(name)


def show(name):
    '''
    .. versionadded:: 2014.7.0

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
    .. versionadded:: 2014.7.0

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
