# -*- coding: utf-8 -*-
'''
Manage and query NPM packages.
'''
from __future__ import absolute_import
try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote

# Import python libs
import json
import logging
import distutils.version  # pylint: disable=import-error,no-name-in-module

# Import salt libs
import salt.utils
import salt.modules.cmdmod
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
            _check_valid_version()
            return True
        else:
            return (False, 'npm execution module could not be loaded '
                           'because the npm binary could not be located')
    except CommandExecutionError as exc:
        return (False, str(exc))


def _check_valid_version():
    '''
    Check the version of npm to ensure this module will work. Currently
    npm must be at least version 1.2.
    '''
    # pylint: disable=no-member
    npm_version = distutils.version.LooseVersion(
        salt.modules.cmdmod.run('npm --version', python_shell=True))
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
            env=None,
            dry_run=False,
            silent=True):
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

    silent
        Whether or not to run NPM install with --silent flag.

        .. versionadded:: Boron

    dry_run
        Whether or not to run NPM install with --dry-run flag.

        .. versionadded:: 2015.8.4

    silent
        Wether or not to run NPM install with --silent flag.

        .. versionadded:: 2015.8.5

    CLI Example:

    .. code-block:: bash

        salt '*' npm.install coffee-script

        salt '*' npm.install coffee-script@1.0.1

    '''
    # Protect against injection
    if pkg:
        pkg = _cmd_quote(pkg)
    if pkgs:
        pkg_list = []
        for item in pkgs:
            pkg_list.append(_cmd_quote(item))
        pkgs = pkg_list
    if registry:
        registry = _cmd_quote(registry)

    cmd = ['npm', 'install']
    if silent:
        cmd.append('--silent')
    cmd.append('--json')

    if dir is None:
        cmd.append(' --global')

    if registry:
        cmd.append(' --registry="{0}"'.format(registry))

    if dry_run:
        cmd.append('--dry-run')

    if pkg:
        cmd.append(pkg)
    elif pkgs:
        cmd.extend(pkgs)

    if env is None:
        env = {}

    if runas:
        uid = salt.utils.get_uid(runas)
        if uid:
            env.update({'SUDO_UID': b'{0}'.format(uid), 'SUDO_USER': b''})

    cmd = ' '.join(cmd)
    result = __salt__['cmd.run_all'](cmd, python_shell=True, cwd=dir, runas=runas, env=env)

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
              runas=None,
              env=None):
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

    env
        Environment variables to set when invoking npm. Uses the same ``env``
        format as the :py:func:`cmd.run <salt.modules.cmdmod.run>` execution
        function.

        .. versionadded:: 2015.5.3

    CLI Example:

    .. code-block:: bash

        salt '*' npm.uninstall coffee-script

    '''
    # Protect against injection
    if pkg:
        pkg = _cmd_quote(pkg)

    if env is None:
        env = {}

    if runas:
        uid = salt.utils.get_uid(runas)
        if uid:
            env.update({'SUDO_UID': b'{0}'.format(uid), 'SUDO_USER': b''})

    cmd = 'npm uninstall'

    if dir is None:
        cmd += ' --global'

    cmd += ' "{0}"'.format(pkg)

    result = __salt__['cmd.run_all'](cmd, python_shell=True, cwd=dir, runas=runas, env=env)

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
    # Protect against injection
    if pkg:
        pkg = _cmd_quote(pkg)

    if env is None:
        env = {}

    if runas:
        uid = salt.utils.get_uid(runas)
        if uid:
            env.update({'SUDO_UID': b'{0}'.format(uid), 'SUDO_USER': b''})

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
            python_shell=True,
            ignore_retcode=True)

    # npm will return error code 1 for both no packages found and an actual
    # error. The only difference between the two cases are if stderr is empty
    if result['retcode'] != 0 and result['stderr']:
        raise CommandExecutionError(result['stderr'])

    return json.loads(result['stdout']).get('dependencies', {})
