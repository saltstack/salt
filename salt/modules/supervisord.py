# -*- coding: utf-8 -*-
'''
Provide the service module for system supervisord or supervisord in a
virtualenv
'''


# Import python libs
from __future__ import absolute_import, unicode_literals, print_function
import os

# Import 3rd-party libs
from salt.ext.six import string_types
from salt.ext.six.moves import configparser  # pylint: disable=import-error

# Import salt libs
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, CommandNotFoundError


def __virtual__():
    # We can't decide at load time whether supervisorctl is present. The
    # function _get_supervisorctl_bin does a much more thorough job and can
    # only be accurate at call time.
    return True


def _get_supervisorctl_bin(bin_env):
    '''
    Return supervisorctl command to call, either from a virtualenv, an argument
    passed in, or from the global modules options
    '''
    cmd = 'supervisorctl'
    if not bin_env:
        which_result = __salt__['cmd.which_bin']([cmd])
        if which_result is None:
            raise CommandNotFoundError(
                'Could not find a `{0}` binary'.format(cmd)
            )
        return which_result

    # try to get binary from env
    if os.path.isdir(bin_env):
        cmd_bin = os.path.join(bin_env, 'bin', cmd)
        if os.path.isfile(cmd_bin):
            return cmd_bin
        raise CommandNotFoundError('Could not find a `{0}` binary'.format(cmd))

    return bin_env


def _ctl_cmd(cmd, name, conf_file, bin_env):
    '''
    Return the command list to use
    '''
    ret = [_get_supervisorctl_bin(bin_env)]
    if conf_file is not None:
        ret += ['-c', conf_file]
    ret.append(cmd)
    if name:
        ret.append(name)
    return ret


def _get_return(ret):
    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return ''


def start(name='all', user=None, conf_file=None, bin_env=None):
    '''
    Start the named service.
    Process group names should not include a trailing asterisk.

    user
        user to run supervisorctl as
    conf_file
        path to supervisord config file
    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor
        installed

    CLI Example:

    .. code-block:: bash

        salt '*' supervisord.start <service>
        salt '*' supervisord.start <group>:
    '''
    if name.endswith(':*'):
        name = name[:-1]
    ret = __salt__['cmd.run_all'](
        _ctl_cmd('start', name, conf_file, bin_env),
        runas=user,
        python_shell=False,
    )
    return _get_return(ret)


def restart(name='all', user=None, conf_file=None, bin_env=None):
    '''
    Restart the named service.
    Process group names should not include a trailing asterisk.

    user
        user to run supervisorctl as
    conf_file
        path to supervisord config file
    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor
        installed

    CLI Example:

    .. code-block:: bash

        salt '*' supervisord.restart <service>
        salt '*' supervisord.restart <group>:
    '''
    if name.endswith(':*'):
        name = name[:-1]
    ret = __salt__['cmd.run_all'](
        _ctl_cmd('restart', name, conf_file, bin_env),
        runas=user,
        python_shell=False,
    )
    return _get_return(ret)


def stop(name='all', user=None, conf_file=None, bin_env=None):
    '''
    Stop the named service.
    Process group names should not include a trailing asterisk.

    user
        user to run supervisorctl as
    conf_file
        path to supervisord config file
    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor
        installed

    CLI Example:

    .. code-block:: bash

        salt '*' supervisord.stop <service>
        salt '*' supervisord.stop <group>:
    '''
    if name.endswith(':*'):
        name = name[:-1]
    ret = __salt__['cmd.run_all'](
        _ctl_cmd('stop', name, conf_file, bin_env),
        runas=user,
        python_shell=False,
    )
    return _get_return(ret)


def add(name, user=None, conf_file=None, bin_env=None):
    '''
    Activates any updates in config for process/group.

    user
        user to run supervisorctl as
    conf_file
        path to supervisord config file
    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor
        installed

    CLI Example:

    .. code-block:: bash

        salt '*' supervisord.add <name>
    '''
    if name.endswith(':'):
        name = name[:-1]
    elif name.endswith(':*'):
        name = name[:-2]
    ret = __salt__['cmd.run_all'](
        _ctl_cmd('add', name, conf_file, bin_env),
        runas=user,
        python_shell=False,
    )
    return _get_return(ret)


def remove(name, user=None, conf_file=None, bin_env=None):
    '''
    Removes process/group from active config

    user
        user to run supervisorctl as
    conf_file
        path to supervisord config file
    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor
        installed

    CLI Example:

    .. code-block:: bash

        salt '*' supervisord.remove <name>
    '''
    if name.endswith(':'):
        name = name[:-1]
    elif name.endswith(':*'):
        name = name[:-2]
    ret = __salt__['cmd.run_all'](
        _ctl_cmd('remove', name, conf_file, bin_env),
        runas=user,
        python_shell=False,
    )
    return _get_return(ret)


def reread(user=None, conf_file=None, bin_env=None):
    '''
    Reload the daemon's configuration files

    user
        user to run supervisorctl as
    conf_file
        path to supervisord config file
    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor
        installed

    CLI Example:

    .. code-block:: bash

        salt '*' supervisord.reread
    '''
    ret = __salt__['cmd.run_all'](
        _ctl_cmd('reread', None, conf_file, bin_env),
        runas=user,
        python_shell=False,
    )
    return _get_return(ret)


def update(user=None, conf_file=None, bin_env=None, name=None):
    '''
    Reload config and add/remove/update as necessary

    user
        user to run supervisorctl as
    conf_file
        path to supervisord config file
    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor
        installed
    name
        name of the process group to update. if none then update any
        process group that has changes

    CLI Example:

    .. code-block:: bash

        salt '*' supervisord.update
    '''

    if isinstance(name, string_types):
        if name.endswith(':'):
            name = name[:-1]
        elif name.endswith(':*'):
            name = name[:-2]

    ret = __salt__['cmd.run_all'](
        _ctl_cmd('update', name, conf_file, bin_env),
        runas=user,
        python_shell=False,
    )
    return _get_return(ret)


def status(name=None, user=None, conf_file=None, bin_env=None):
    '''
    List programs and its state

    user
        user to run supervisorctl as
    conf_file
        path to supervisord config file
    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor
        installed

    CLI Example:

    .. code-block:: bash

        salt '*' supervisord.status
    '''
    all_process = {}
    for line in status_raw(name, user, conf_file, bin_env).splitlines():
        if len(line.split()) > 2:
            process, state, reason = line.split(None, 2)
        else:
            process, state, reason = line.split() + ['']
        all_process[process] = {'state': state, 'reason': reason}
    return all_process


def status_raw(name=None, user=None, conf_file=None, bin_env=None):
    '''
    Display the raw output of status

    user
        user to run supervisorctl as
    conf_file
        path to supervisord config file
    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor
        installed

    CLI Example:

    .. code-block:: bash

        salt '*' supervisord.status_raw
    '''
    ret = __salt__['cmd.run_all'](
        _ctl_cmd('status', name, conf_file, bin_env),
        runas=user,
        python_shell=False,
    )
    return _get_return(ret)


def custom(command, user=None, conf_file=None, bin_env=None):
    '''
    Run any custom supervisord command

    user
        user to run supervisorctl as
    conf_file
        path to supervisord config file
    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor
        installed

    CLI Example:

    .. code-block:: bash

        salt '*' supervisord.custom "mstop '*gunicorn*'"
    '''
    ret = __salt__['cmd.run_all'](
        _ctl_cmd(command, None, conf_file, bin_env),
        runas=user,
        python_shell=False,
    )
    return _get_return(ret)


# TODO: try to find a way to use the supervisor python module to read the
# config information
def _read_config(conf_file=None):
    '''
    Reads the config file using configparser
    '''
    if conf_file is None:
        paths = ('/etc/supervisor/supervisord.conf', '/etc/supervisord.conf')
        for path in paths:
            if os.path.exists(path):
                conf_file = path
                break
    if conf_file is None:
        raise CommandExecutionError('No suitable config file found')
    config = configparser.ConfigParser()
    try:
        config.read(conf_file)
    except (IOError, OSError) as exc:
        raise CommandExecutionError(
            'Unable to read from {0}: {1}'.format(conf_file, exc)
        )
    return config


def options(name, conf_file=None):
    '''
    .. versionadded:: 2014.1.0

    Read the config file and return the config options for a given process

    name
        Name of the configured process
    conf_file
        path to supervisord config file

    CLI Example:

    .. code-block:: bash

        salt '*' supervisord.options foo
    '''
    config = _read_config(conf_file)
    section_name = 'program:{0}'.format(name)
    if section_name not in config.sections():
        raise CommandExecutionError('Process \'{0}\' not found'.format(name))
    ret = {}
    for key, val in config.items(section_name):
        val = salt.utils.stringutils.to_num(val.split(';')[0].strip())
        # pylint: disable=maybe-no-member
        if isinstance(val, string_types):
            if val.lower() == 'true':
                val = True
            elif val.lower() == 'false':
                val = False
        # pylint: enable=maybe-no-member
        ret[key] = val
    return ret
