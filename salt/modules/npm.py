'''
Manage and query NPM packages.
'''

import json

from salt.exceptions import CommandExecutionError

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
    cmd = 'npm install --json'

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
    cmd = 'npm list --json'

    if dir is None:
        cmd += ' --global'

    if pkg:
        cmd += ' ' + pkg

    result = __salt__['cmd.run_all'](cmd, cwd=dir)

    if result['retcode'] != 0:
        raise CommandExecutionError(result['stderr'])

    return json.loads(result['stdout']).get('dependencies', {})
