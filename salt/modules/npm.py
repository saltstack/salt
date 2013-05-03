'''
Manage and query NPM packages.
'''

import json
import distutils.version

# Import salt libs
import salt.utils

from salt.exceptions import CommandExecutionError

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

    CLI example::

        salt '*' npm.install coffee-script

    '''
    if not _valid_version():
        return '"{0}" is not available.'.format('npm.install')

    cmd = 'npm install --silent --json'

    if dir is None:
        cmd += ' --global'

    if pkg:
        cmd += ' ' + pkg

    result = __salt__['cmd.run_all'](cmd, cwd=dir, runas=runas)

    if result['retcode'] != 0:
        raise CommandExecutionError(result['stderr'])

    lines = result['stdout'].splitlines()

    while ' -> ' in lines[0]:
        lines = lines[1:]

    # Strip all lines until JSON output starts
    for i in lines:
        if i.startswith("{"):
            break
        else:
            lines = lines[1:]        

    return json.loads(''.join(lines))

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

    CLI example::

        salt '*' npm.uninstall coffee-script

    '''
    if not _valid_version():
        return '"{0}" is not available.'.format('npm.uninstall')

    cmd = 'npm uninstall'

    if dir is None:
        cmd += ' --global'

    cmd += ' ' + pkg

    result = __salt__['cmd.run_all'](cmd, cwd=dir, runas=runas)

    if result['retcode'] != 0:
        raise CommandExecutionError(result['stderr'])

def list(pkg=None,
         dir=None):
    '''
    List installed NPM packages.

    If no directory is specified, this will return the list of globally-
    installed packages.

    pkg
        Limit package listing by name

    dir
        The directory whose packages will be listed, or None for global
        installation

    CLI example::

        salt '*' npm.list

    '''
    if not _valid_version():
        return '"{0}" is not available.'.format('npm.list')

    cmd = 'npm list --json'

    if dir is None:
        cmd += ' --global'

    if pkg:
        cmd += ' ' + pkg

    result = __salt__['cmd.run_all'](cmd, cwd=dir)

    if result['retcode'] != 0:
        raise CommandExecutionError(result['stderr'])

    return json.loads(result['stdout']).get('dependencies', {})
