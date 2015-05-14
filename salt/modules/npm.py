# -*- coding: utf-8 -*-
'''
Manage and query NPM packages.
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
    Only work when npm is installed.
    '''
    try:
        if salt.utils.which('npm') is not None:
            _check_valid_version(__salt__)
            return True
        else:
            return (False, 'npm execution module could not be loaded '
                           'because the npm binary could not be located')
    except CommandExecutionError as exc:
        return (False, str(exc))


def _check_valid_version(salt):
    '''
    Check the version of npm to ensure this module will work. Currently
    npm must be at least version 1.2.
    '''
    # pylint: disable=no-member
    npm_version = distutils.version.LooseVersion(
        salt['cmd.run']('npm --version'))
    valid_version = distutils.version.LooseVersion('1.2')
    # pylint: enable=no-member
    if npm_version < valid_version:
        raise CommandExecutionError(
            '\'npm\' is not recent enough({0} < {1}). Please Upgrade.'.format(
                npm_version, valid_version
            )
        )


def install(pkg=None,
            pkgs=None,
            dir=None,
            runas=None,
            registry=None,
            env=None):
    '''
    Install an NPM package.

    If no directory is specified, the package will be installed globally. If
    no package is specified, the dependencies (from package.json) of the
    package in the given directory will be installed.

    pkg
        A package name in any format accepted by NPM, including a version
        identifier

    pkgs
        A list of package names in the same format as the ``name`` parameter

        .. versionadded:: 2014.7.0

    dir
        The target directory in which to install the package, or None for
        global installation

    runas
        The user to run NPM with

    registry
        The NPM registry to install the package from.

        .. versionadded:: 2014.7.0

    env
        Environment variables to set when invoking npm. Uses the same ``env``
        format as the :py:func:`cmd.run <salt.modules.cmdmod.run>` execution
        function.

        .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' npm.install coffee-script

        salt '*' npm.install coffee-script@1.0.1

    '''

    cmd = 'npm install --silent --json'

    if dir is None:
        cmd += ' --global'

    if registry:
        cmd += ' --registry="{0}"'.format(registry)

    if pkg:
        cmd += ' "{0}"'.format(pkg)
    elif pkgs:
        cmd += ' "{0}"'.format('" "'.join(pkgs))

    result = __salt__['cmd.run_all'](cmd, python_shell=False, cwd=dir, runas=runas, env=env)

    if result['retcode'] != 0:
        raise CommandExecutionError(result['stderr'])

    # npm >1.2.21 is putting the output to stderr even though retcode is 0
    npm_output = result['stdout'] or result['stderr']
    try:
        return json.loads(npm_output)
    except ValueError:
        # Not JSON! Try to coax the json out of it!
        pass

    lines = npm_output.splitlines()
    log.error(lines)

    while lines:
        # Strip all lines until JSON output starts
        while not lines[0].startswith('{') and not lines[0].startswith('['):
            lines = lines[1:]

        try:
            return json.loads(''.join(lines))
        except ValueError:
            lines = lines[1:]

    # Still no JSON!! Return the stdout as a string
    return npm_output


def uninstall(pkg,
              dir=None,
              runas=None):
    '''
    Uninstall an NPM package.

    If no directory is specified, the package will be uninstalled globally.

    pkg
        A package name in any format accepted by NPM

    dir
        The target directory from which to uninstall the package, or None for
        global installation

    runas
        The user to run NPM with

    CLI Example:

    .. code-block:: bash

        salt '*' npm.uninstall coffee-script

    '''

    cmd = 'npm uninstall'

    if dir is None:
        cmd += ' --global'

    cmd += ' "{0}"'.format(pkg)

    result = __salt__['cmd.run_all'](cmd, python_shell=False, cwd=dir, runas=runas)

    if result['retcode'] != 0:
        log.error(result['stderr'])
        return False
    return True


def list_(pkg=None,
            dir=None,
            runas=None,
            env=None):
    '''
    List installed NPM packages.

    If no directory is specified, this will return the list of globally-
    installed packages.

    pkg
        Limit package listing by name

    dir
        The directory whose packages will be listed, or None for global
        installation

    runas
        The user to run NPM with

        .. versionadded:: 2014.7.0

    env
        Environment variables to set when invoking npm. Uses the same ``env``
        format as the :py:func:`cmd.run <salt.modules.cmdmod.run>` execution
        function.

        .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' npm.list

    '''

    cmd = 'npm list --silent --json'

    if dir is None:
        cmd += ' --global'

    if pkg:
        cmd += ' "{0}"'.format(pkg)

    result = __salt__['cmd.run_all'](
            cmd,
            cwd=dir,
            runas=runas,
            env=env,
            python_shell=False,
            ignore_retcode=True)

    # npm will return error code 1 for both no packages found and an actual
    # error. The only difference between the two cases are if stderr is empty
    if result['retcode'] != 0 and result['stderr']:
        raise CommandExecutionError(result['stderr'])

    return json.loads(result['stdout']).get('dependencies', {})
