# -*- coding: utf-8 -*-
'''
Manage and query NPM packages.
'''

# Import python libs
import json
import logging
import distutils.version  # pylint: disable=E0611

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
    if salt.utils.which('npm'):
        return 'npm'
    return False


def _valid_version():
    '''
    Check the version of npm to ensure this module will work. Currently
    npm must be at least version 1.2.
    '''
    npm_version = distutils.version.LooseVersion(
        __salt__['cmd.run']('npm --version'))
    valid_version = distutils.version.LooseVersion('1.2')
    return npm_version >= valid_version


def install(pkg=None,
            dir=None,
            runas=None):
    '''
    Install an NPM package.

    If no directory is specified, the package will be installed globally. If
    no package is specified, the dependencies (from package.json) of the
    package in the given directory will be installed.

    pkg
        A package name in any format accepted by NPM

    dir
        The target directory in which to install the package, or None for
        global installation

    runas
        The user to run NPM with

    CLI Example:

    .. code-block:: bash

        salt '*' npm.install coffee-script

    '''
    if not _valid_version():
        return '{0!r} is not available.'.format('npm.install')

    cmd = 'npm install --silent --json'

    if dir is None:
        cmd += ' --global'

    if pkg:
        cmd += ' "{0}"'.format(pkg)

    result = __salt__['cmd.run_all'](cmd, cwd=dir, runas=runas)

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

    # Strip all lines until JSON output starts
    while not lines[0].startswith('{') and not lines[0].startswith('['):
        lines = lines[1:]

    try:
        return json.loads(''.join(lines))
    except ValueError:
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
    if not _valid_version():
        log.error('{0!r} is not available.'.format('npm.uninstall'))
        return False

    cmd = 'npm uninstall'

    if dir is None:
        cmd += ' --global'

    cmd += ' "{0}"'.format(pkg)

    result = __salt__['cmd.run_all'](cmd, cwd=dir, runas=runas)

    if result['retcode'] != 0:
        log.error(result['stderr'])
        return False
    return True


def list_(pkg=None, dir=None):
    '''
    List installed NPM packages.

    If no directory is specified, this will return the list of globally-
    installed packages.

    pkg
        Limit package listing by name

    dir
        The directory whose packages will be listed, or None for global
        installation

    CLI Example:

    .. code-block:: bash

        salt '*' npm.list

    '''
    if not _valid_version():
        return '{0!r} is not available.'.format('npm.list')

    cmd = 'npm list --json'

    if dir is None:
        cmd += ' --global'

    if pkg:
        cmd += ' "{0}"'.format(pkg)

    result = __salt__['cmd.run_all'](cmd, cwd=dir)

    # npm will return error code 1 for both no packages found and an actual
    # error. The only difference between the two cases are if stderr is empty
    if result['retcode'] != 0 and result['stderr']:
        raise CommandExecutionError(result['stderr'])

    return json.loads(result['stdout']).get('dependencies', {})
