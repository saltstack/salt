# -*- coding: utf-8 -*-
'''
Installation of Bower Packages
==============================

These states manage the installed packages using Bower.
Note that npm, git and bower must be installed for these states to be
available, so bower states should include requisites to pkg.installed states
for the packages which provide npm and git (simply ``npm`` and ``git`` in most
cases), and npm.installed state for the package which provides bower.

Example:

.. code-block:: yaml

    npm:
      pkg.installed
    git:
      pkg.installed
    bower:
      npm.installed
      require:
        - pkg: npm
        - pkg: git

    underscore:
      bower.installed:
        - dir: /path/to/project
        - require:
          - npm: bower
'''

from __future__ import absolute_import

# Import salt libs
from salt.exceptions import CommandExecutionError, CommandNotFoundError

# Import 3rd-party libs
import salt.ext.six as six


def __virtual__():
    '''
    Only load if the bower module is available in __salt__
    '''
    return 'bower' if 'bower.list' in __salt__ else False


def installed(name,
              dir,
              pkgs=None,
              user=None,
              env=None):
    '''
    Verify that the given package is installed and is at the correct version
    (if specified).

    .. code-block:: yaml

        underscore:
          bower.installed:
            - dir: /path/to/project
            - user: someuser

        jquery#2.0:
          bower.installed:
            - dir: /path/to/project

    name
        The package to install

    dir
        The target directory in which to install the package

    pkgs
        A list of packages to install with a single Bower invocation;
        specifying this argument will ignore the ``name`` argument

    user
        The user to run Bower with

    env
        A list of environment variables to be set prior to execution. The
        format is the same as the :py:func:`cmd.run <salt.states.cmd.run>`.
        state function.

    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if pkgs is not None:
        pkg_list = pkgs
    else:
        pkg_list = [name]

    try:
        installed_pkgs = __salt__['bower.list'](dir=dir, runas=user, env=env)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = False
        ret['comment'] = 'Error looking up \'{0}\': {1}'.format(name, err)
        return ret
    else:
        installed_pkgs = dict((p, info) for p, info in
                              six.iteritems(installed_pkgs))

    pkgs_satisfied = []
    pkgs_to_install = []
    for pkg in pkg_list:
        pkg_name, _, pkg_ver = pkg.partition('#')
        pkg_name = pkg_name.strip()

        if pkg_name not in installed_pkgs:
            pkgs_to_install.append(pkg)
            continue

        if pkg_name in installed_pkgs:
            installed_pkg = installed_pkgs[pkg_name]
            installed_pkg_ver = installed_pkg.get('pkgMeta').get('version')
            installed_name_ver = '{0}#{1}'.format(
                pkg_name,
                installed_pkg_ver)

            # If given an explicit version check the installed version matches.
            if pkg_ver:
                if installed_pkg_ver != pkg_ver:
                    pkgs_to_install.append(pkg)
                else:
                    pkgs_satisfied.append(installed_name_ver)

                continue
            else:
                pkgs_satisfied.append(installed_name_ver)
                continue

    if __opts__['test']:
        ret['result'] = None

        comment_msg = []
        if pkgs_to_install:
            comment_msg.append(
                'Bower package(s) \'{0}\' are set to be installed'.format(
                    ', '.join(pkgs_to_install)))

            ret['changes'] = {'old': [], 'new': pkgs_to_install}

        if pkgs_satisfied:
            comment_msg.append(
                'Package(s) \'{0}\' satisfied by {1}'.format(
                    ', '.join(pkg_list), ', '.join(pkgs_satisfied)))

        ret['comment'] = '. '.join(comment_msg)
        return ret

    if not pkgs_to_install:
        ret['result'] = True
        ret['comment'] = ('Package(s) \'{0}\' satisfied by {1}'.format(
            ', '.join(pkg_list), ', '.join(pkgs_satisfied)))
        return ret

    try:
        cmd_args = {
            'pkg': None,
            'dir': dir,
            'pkgs': None,
            'runas': user,
            'env': env,
        }

        if pkgs is not None:
            cmd_args['pkgs'] = pkgs
        else:
            cmd_args['pkg'] = pkg_name

        call = __salt__['bower.install'](**cmd_args)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = False
        ret['comment'] = 'Error installing \'{0}\': {1}'.format(
                ', '.join(pkg_list), err)
        return ret

    if call:
        ret['result'] = True
        ret['changes'] = {'old': [], 'new': pkgs_to_install}
        ret['comment'] = 'Package(s) \'{0}\' successfully installed'.format(
                ', '.join(pkgs_to_install))
    else:
        ret['result'] = False
        ret['comment'] = 'Could not install package(s) \'{0}\''.format(
                ', '.join(pkg_list))

    return ret


def removed(name, dir, user=None):
    '''
    Verify that the given package is not installed.

    dir
        The target directory in which to install the package

    user
        The user to run Bower with

    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    try:
        installed_pkgs = __salt__['bower.list'](dir=dir, runas=user)
    except (CommandExecutionError, CommandNotFoundError) as err:
        ret['result'] = False
        ret['comment'] = 'Error removing \'{0}\': {1}'.format(name, err)
        return ret

    if name not in installed_pkgs:
        ret['result'] = True
        ret['comment'] = 'Package \'{0}\' is not installed'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Package \'{0}\' is set to be removed'.format(name)
        return ret

    try:
        if __salt__['bower.uninstall'](pkg=name, dir=dir, runas=user):
            ret['result'] = True
            ret['changes'] = {name: 'Removed'}
            ret['comment'] = 'Package \'{0}\' was successfully removed'.format(
                name)
        else:
            ret['result'] = False
            ret['comment'] = 'Error removing \'{0}\''.format(name)
    except (CommandExecutionError, CommandNotFoundError) as err:
        ret['result'] = False
        ret['comment'] = 'Error removing \'{0}\': {1}'.format(name, err)

    return ret


def bootstrap(name, user=None):
    '''
    Bootstraps a frontend distribution.

    Will execute 'bower install' on the specified directory.

    user
        The user to run Bower with

    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Directory \'{0}\' is set to be bootstrapped'.format(
            name)
        return ret

    try:
        call = __salt__['bower.install'](pkg=None, dir=name, runas=user)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = False
        ret['comment'] = 'Error bootstrapping \'{0}\': {1}'.format(name, err)
        return ret

    if not call:
        ret['result'] = True
        ret['comment'] = 'Directory is already bootstrapped'
        return ret

    ret['result'] = True
    ret['changes'] = {name: 'Bootstrapped'}
    ret['comment'] = 'Directory was successfully bootstrapped'

    return ret


def pruned(name, user=None, env=None):
    '''
    .. versionadded:: Nitrogen

    Cleans up local bower_components directory.

    Will execute 'bower prune' on the specified directory (param: name)

    user
        The user to run Bower with

    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Directory \'{0}\' is set to be pruned'.format(
            name)
        return ret

    try:
        call = __salt__['bower.prune'](dir=name, runas=user, env=env)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = False
        ret['comment'] = 'Error pruning \'{0}\': {1}'.format(name, err)
        return ret

    ret['result'] = True
    if call:
        ret['comment'] = 'Directory \'{0}\' was successfully pruned'.format(name)
        ret['changes'] = {'old': [], 'new': call}
    else:
        ret['comment'] = 'No packages were pruned from directory \'{0}\''.format(name)

    return ret
