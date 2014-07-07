# -*- coding: utf-8 -*-
'''
Module for getting information about syslog-ng
===============================================

:maintainer:    Tibor Benke <btibi@sch.bme.hu>
:maturity:      new
:depends:       cmd
:platform:      all

This is module is capable of managing syslog-ng instances which were not
installed via a package manager. Users can use a directory as a parameter
in the case of most functions, which contains the syslog-ng and syslog-ng-ctl
binaries.
'''

from __future__ import generators, print_function, with_statement

import os
import logging
import salt
import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def _run_command(cmd, options=()):
    '''
    Runs the command cmd with options as its CLI parameters and returns the result
    as a dictionary.
    '''
    cmd_with_params = [cmd]
    cmd_with_params.extend(options)

    cmd_to_run = " ".join(cmd_with_params)

    try:
        return __salt__['cmd.run_all'](cmd_to_run)
    except Exception as err:
        log.error(str(err))
        raise CommandExecutionError("Unable to run command: " + str(type(err)))


def _add_to_path_envvar(directory):
    '''
    Adds directory to the PATH environment variable and returns the original
    one.
    '''
    orig_path = os.environ["PATH"]
    if directory:
        if not os.path.isdir(directory):
            log.error("The given parameter is not a directory")

        os.environ["PATH"] = "{0}{1}{2}".format(orig_path, os.pathsep, directory)

    return orig_path


def _restore_path_envvar(original):
    '''
    Sets the PATH environment variable to the parameter.
    '''
    if original:
        os.environ["PATH"] = original


def _run_command_in_extended_path(syslog_ng_sbin_dir, command, params):
    '''
    Runs the given command in an environment, where the syslog_ng_sbin_dir is
    added then removed from the PATH.
    '''
    orig_path = _add_to_path_envvar(syslog_ng_sbin_dir)

    if not salt.utils.which(command):
        error_message = "Unable to execute the command '{0}'. It is not in the PATH.".format(command)
        log.error(error_message)
        _restore_path_envvar(orig_path)
        raise CommandExecutionError(error_message)

    ret = _run_command(command, options=params)
    _restore_path_envvar(orig_path)
    return ret


def _format_return_data(retcode, stdout=None, stderr=None):
    '''
    Creates a dictionary from the parameters, which can be used to return data
    to Salt.
    '''
    ret = {"retcode": retcode}
    if stdout is not None:
        ret["stdout"] = stdout
    if stderr is not None:
        ret["stderr"] = stderr
    return ret


def config_test(syslog_ng_sbin_dir=None, cfgfile=None):
    '''
    Runs syntax check against cfgfile. If syslog_ng_sbin_dir is specified, it
    is added to the PATH during the test.

    CLI Example:

    .. code-block:: bash

        salt '*' syslog_ng.config_test
        salt '*' syslog_ng.config_test /home/user/install/syslog-ng/sbin
        salt '*' syslog_ng.config_test /home/user/install/syslog-ng/sbin /etc/syslog-ng/syslog-ng.conf
    '''
    params = ["--syntax-only", ]
    if cfgfile:
        params.append("--cfgfile={0}".format(cfgfile))

    try:
        ret = _run_command_in_extended_path(syslog_ng_sbin_dir, "syslog-ng", params)
    except CommandExecutionError as err:
        return _format_return_data(retcode=-1, stderr=str(err))

    retcode = ret.get("retcode", -1)
    stderr = ret.get("stderr", None)
    stdout = ret.get("stdout", None)
    return _format_return_data(retcode, stdout, stderr)


def version(syslog_ng_sbin_dir=None):
    '''
    Returns the version of the installed syslog-ng. If syslog_ng_sbin_dir is specified, it
    is added to the PATH during the execution of the command syslog-ng.

    CLI Example:

    .. code-block:: bash

        salt '*' syslog_ng.version
        salt '*' syslog_ng.version /home/user/install/syslog-ng/sbin
    '''
    try:
        ret = _run_command_in_extended_path(syslog_ng_sbin_dir, "syslog-ng", ("-V",))
    except CommandExecutionError as err:
        return _format_return_data(retcode=-1, stderr=str(err))

    if ret["retcode"] != 0:
        return _format_return_data(ret["retcode"], stderr=ret["stderr"], stdout=ret["stdout"])

    lines = ret["stdout"].split("\n")
    # The format of the first line in the output is:
    # syslog-ng 3.6.0alpha0
    version_line_index = 0
    version_column_index = 1
    v = lines[version_line_index].split()[version_column_index]
    return _format_return_data(0, stdout=v)


def modules(syslog_ng_sbin_dir=None):
    '''
    Returns the available modules. If syslog_ng_sbin_dir is specified, it
    is added to the PATH during the execution of the command syslog-ng.

    CLI Example:

    .. code-block:: bash

        salt '*' syslog_ng.modules
        salt '*' syslog_ng.modules /home/user/install/syslog-ng/sbin
    '''
    try:
        ret = _run_command_in_extended_path(syslog_ng_sbin_dir, "syslog-ng", ("-V",))
    except CommandExecutionError as err:
        return _format_return_data(retcode=-1, stderr=str(err))

    if ret["retcode"] != 0:
        return _format_return_data(ret["retcode"], ret.get("stdout", None), ret.get("stderr", None))

    lines = ret["stdout"].split("\n")
    for i, line in enumerate(lines):
        if line.startswith("Available-Modules"):
            label, installed_modules = line.split()
            return _format_return_data(ret["retcode"], stdout=installed_modules)
    return _format_return_data(-1, stderr="Unable to find the modules.")


def stats(syslog_ng_sbin_dir=None):
    '''
    Returns statistics from the running syslog-ng instance. If syslog_ng_sbin_dir is specified, it
    is added to the PATH during the execution of the command syslog-ng-ctl.

    CLI Example:

    .. code-block:: bash

        salt '*' syslog_ng.stats
        salt '*' syslog_ng.stats /home/user/install/syslog-ng/sbin
    '''
    try:
        ret = _run_command_in_extended_path(syslog_ng_sbin_dir, "syslog-ng-ctl", ("stats",))
    except CommandExecutionError as err:
        return _format_return_data(retcode=-1, stderr=str(err))

    return _format_return_data(ret["retcode"], ret.get("stdout", None), ret.get("stderr", None))
