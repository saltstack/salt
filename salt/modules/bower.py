# -*- coding: utf-8 -*-
'''
Manage and query Bower packages
===============================

This module manages the installed packages using Bower.
Note that npm, git and bower must be installed for this module to be
available.

'''
from __future__ import absolute_import

# Import python libs
import json
import logging
import distutils.version  # pylint: disable=import-error,no-name-in-module

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError


log = logging.getLogger(__name__)

# Function alias to make sure not to shadow built-in's
__func_alias__ = {
    'list_': 'list'
}


def __virtual__():
    '''
    Only work when Bower is installed
    '''
    return salt.utils.which('bower') is not None


def _check_valid_version():
    '''
    Check the version of Bower to ensure this module will work. Currently
    bower must be at least version 1.3.
    '''
    # pylint: disable=no-member
    bower_version = distutils.version.LooseVersion(
        __salt__['cmd.run']('bower --version'))
    valid_version = distutils.version.LooseVersion('1.3')
    # pylint: enable=no-member
    if bower_version < valid_version:
        raise CommandExecutionError(
            '\'bower\' is not recent enough({0} < {1}). '
            'Please Upgrade.'.format(
                bower_version, valid_version
            )
        )


def install(pkg,
            dir,
            pkgs=None,
            runas=None,
            env=None):
    '''
    Install a Bower package.

    If no package is specified, the dependencies (from bower.json) of the
    package in the given directory will be installed.

    pkg
        A package name in any format accepted by Bower, including a version
        identifier

    dir
        The target directory in which to install the package

    pkgs
        A list of package names in the same format as the ``pkg`` parameter

    runas
        The user to run Bower with

    env
        Environment variables to set when invoking Bower. Uses the same ``env``
        format as the :py:func:`cmd.run <salt.modules.cmdmod.run>` execution
        function.

    CLI Example:

    .. code-block:: bash

        salt '*' bower.install underscore /path/to/project

        salt '*' bower.install jquery#2.0 /path/to/project

    '''
    _check_valid_version()

    cmd = 'bower install'
    cmd += ' --config.analytics false'
    cmd += ' --config.interactive false'
    cmd += ' --allow-root'
    cmd += ' --json'

    if pkg:
        cmd += ' "{0}"'.format(pkg)
    elif pkgs:
        cmd += ' "{0}"'.format('" "'.join(pkgs))

    result = __salt__['cmd.run_all'](cmd,
                                     cwd=dir,
                                     runas=runas,
                                     env=env,
                                     python_shell=False)

    if result['retcode'] != 0:
        raise CommandExecutionError(result['stderr'])

    # If package is already installed, Bower will emit empty dict to STDOUT
    stdout = json.loads(result['stdout'])
    return stdout != {}


def uninstall(pkg, dir, runas=None, env=None):
    '''
    Uninstall a Bower package.

    pkg
        A package name in any format accepted by Bower

    dir
        The target directory from which to uninstall the package

    runas
        The user to run Bower with

    env
        Environment variables to set when invoking Bower. Uses the same ``env``
        format as the :py:func:`cmd.run <salt.modules.cmdmod.run>` execution
        function.


    CLI Example:

    .. code-block:: bash

        salt '*' bower.uninstall underscore /path/to/project

    '''
    _check_valid_version()

    cmd = 'bower uninstall'
    cmd += ' --config.analytics false'
    cmd += ' --config.interactive false'
    cmd += ' --allow-root'
    cmd += ' --json'
    cmd += ' "{0}"'.format(pkg)

    result = __salt__['cmd.run_all'](cmd,
                                     cwd=dir,
                                     runas=runas,
                                     env=env,
                                     python_shell=False)

    if result['retcode'] != 0:
        raise CommandExecutionError(result['stderr'])

    # If package is not installed, Bower will emit empty dict to STDOUT
    stdout = json.loads(result['stdout'])
    return stdout != {}


def list_(dir, runas=None, env=None):
    '''
    List installed Bower packages.

    dir
        The directory whose packages will be listed

    runas
        The user to run Bower with

    env
        Environment variables to set when invoking Bower. Uses the same ``env``
        format as the :py:func:`cmd.run <salt.modules.cmdmod.run>` execution
        function.

    CLI Example:

    .. code-block:: bash

        salt '*' bower.list /path/to/project

    '''
    _check_valid_version()

    cmd = 'bower list --json'
    cmd += ' --config.analytics false'
    cmd += ' --config.interactive false'
    cmd += ' --offline'
    cmd += ' --allow-root'

    result = __salt__['cmd.run_all'](cmd,
                                     cwd=dir,
                                     runas=runas,
                                     env=env,
                                     python_shell=False)

    if result['retcode'] != 0:
        raise CommandExecutionError(result['stderr'])

    return json.loads(result['stdout'])['dependencies']
