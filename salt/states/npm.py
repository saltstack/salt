# -*- coding: utf-8 -*-
'''
Installation of NPM Packages
============================

These states manage the installed packages for node.js using the Node Package
Manager (npm). Note that npm must be installed for these states to be
available, so npm states should include a requisite to a pkg.installed state
for the package which provides npm (simply ``npm`` in most cases). Example:

.. code-block:: yaml

    npm:
      pkg.installed

    yaml:
      npm.installed:
        - require:
          - pkg: npm
'''

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, CommandNotFoundError


def __virtual__():
    '''
    Only load if the npm module is available in __salt__
    '''
    return 'npm' if 'npm.list' in __salt__ else False


def installed(name,
              pkgs=None,
              dir=None,
              runas=None,
              user=None,
              force_reinstall=False,
              registry=None):
    '''
    Verify that the given package is installed and is at the correct version
    (if specified).

    .. code-block:: yaml

        coffee-script:
          npm:
            - installed
            - user: someuser

        coffee-script@1.0.1:
          npm:
            - installed

    name
        The package to install

    pkgs
        A list of packages to install with a single npm invocation; specifying
        this argument will ignore the ``name`` argument

        .. versionadded:: 2014.7

    dir
        The target directory in which to install the package, or None for
        global installation

    runas
        The user to run NPM with

        .. deprecated:: 0.17.0

    user
        The user to run NPM with

        .. versionadded:: 0.17.0

    registry
        The NPM registry from which to install the package

        .. versionadded:: 2014.7.0

    force_reinstall
        Install the package even if it is already installed
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    salt.utils.warn_until(
        'Lithium',
        'Please remove \'runas\' support at this stage. \'user\' support was '
        'added in 0.17.0',
        _dont_call_warnings=True
    )
    if runas:
        # Warn users about the deprecation
        ret.setdefault('warnings', []).append(
            'The \'runas\' argument is being deprecated in favor of \'user\', '
            'please update your state files.'
        )
    if user is not None and runas is not None:
        # user wins over runas but let warn about the deprecation.
        ret.setdefault('warnings', []).append(
            'Passed both the \'runas\' and \'user\' arguments. Please don\'t. '
            '\'runas\' is being ignored in favor of \'user\'.'
        )
        runas = None
    elif runas is not None:
        # Support old runas usage
        user = runas
        runas = None

    if pkgs is not None:
        pkg_list = pkgs
    else:
        pkg_list = [name]

    try:
        installed_pkgs = __salt__['npm.list'](dir=dir)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = False
        ret['comment'] = 'Error looking up {0!r}: {1}'.format(name, err)
        return ret
    else:
        installed_pkgs = dict((p.lower(), info)
                for p, info in installed_pkgs.items())

    pkgs_satisfied = []
    pkgs_to_install = []
    for pkg_name in pkg_list:
        prefix = pkg_name.split('@')[0].strip()

        if prefix.lower() in installed_pkgs:
            if force_reinstall is False:
                pkgs_satisfied.append('{1}@{2}'.format(
                        pkg_name,
                        prefix,
                        installed_pkgs[prefix.lower()]['version']))
        else:
            pkgs_to_install.append(pkg_name)

    if __opts__['test']:
        ret['result'] = None

        comment_msg = []
        if pkgs_to_install:
            comment_msg.append('NPM package(s) {0!r} are set to be installed'
                .format(', '.join(pkgs_to_install)))

            ret['changes'] = {'old': [], 'new': pkgs_to_install}

        if pkgs_satisfied:
            comment_msg.append('Package(s) {0!r} satisfied by {1}'
                .format(', '.join(pkg_list), ', '.join(pkgs_satisfied)))

        ret['comment'] = '. '.join(comment_msg)
        return ret

    if not pkgs_to_install:
        ret['result'] = True
        ret['comment'] = ('Package(s) {0!r} satisfied by {1}'
                .format(', '.join(pkg_list), ', '.join(pkgs_satisfied)))
        return ret

    try:
        cmd_args = {
            'dir': dir,
            'runas': user,
            'registry': registry,
        }

        if pkgs is not None:
            cmd_args['pkgs'] = pkgs
        else:
            cmd_args['pkg'] = pkg_name

        call = __salt__['npm.install'](**cmd_args)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = False
        ret['comment'] = 'Error installing {0!r}: {1}'.format(
                ', '.join(pkg_list), err)
        return ret

    if call and (isinstance(call, list) or isinstance(call, dict)):
        ret['result'] = True
        ret['changes'] = {'old': [], 'new': pkgs_to_install}
        ret['comment'] = 'Package(s) {0!r} were successfully installed'.format(
                ', '.join(pkgs_to_install))
    else:
        ret['result'] = False
        ret['comment'] = 'Could not install package(s) {0!r}'.format(
                ', '.join(pkg_list))

    return ret


def removed(name,
            dir=None,
            runas=None,
            user=None):
    '''
    Verify that the given package is not installed.

    dir
        The target directory in which to install the package, or None for
        global installation

    runas
        The user to run NPM with

        .. deprecated:: 0.17.0

    user
        The user to run NPM with

        .. versionadded:: 0.17.0
    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    salt.utils.warn_until(
        'Lithium',
        'Please remove \'runas\' support at this stage. \'user\' support was '
        'added in 0.17.0',
        _dont_call_warnings=True
    )
    if runas:
        # Warn users about the deprecation
        ret.setdefault('warnings', []).append(
            'The \'runas\' argument is being deprecated in favor of \'user\', '
            'please update your state files.'
        )
    if user is not None and runas is not None:
        # user wins over runas but let warn about the deprecation.
        ret.setdefault('warnings', []).append(
            'Passed both the \'runas\' and \'user\' arguments. Please don\'t. '
            '\'runas\' is being ignored in favor of \'user\'.'
        )
        runas = None
    elif runas is not None:
        # Support old runas usage
        user = runas
        runas = None

    try:
        installed_pkgs = __salt__['npm.list'](dir=dir)
    except (CommandExecutionError, CommandNotFoundError) as err:
        ret['result'] = False
        ret['comment'] = 'Error uninstalling {0!r}: {1}'.format(name, err)
        return ret

    if name not in installed_pkgs:
        ret['result'] = True
        ret['comment'] = 'Package {0!r} is not installed'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Package {0!r} is set to be removed'.format(name)
        return ret

    if __salt__['npm.uninstall'](pkg=name, dir=dir, runas=user):
        ret['result'] = True
        ret['changes'][name] = 'Removed'
        ret['comment'] = 'Package {0!r} was successfully removed'.format(name)
    else:
        ret['result'] = False
        ret['comment'] = 'Error removing package {0!r}'.format(name)

    return ret


def bootstrap(name,
              runas=None,
              user=None):
    '''
    Bootstraps a node.js application.

    will execute npm install --json on the specified directory


    runas
        The user to run NPM with

        .. deprecated:: 0.17.0

    user
        The user to run NPM with

        .. versionadded:: 0.17.0


    '''
    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}
    salt.utils.warn_until(
        'Lithium',
        'Please remove \'runas\' support at this stage. \'user\' support was '
        'added in 0.17.0',
        _dont_call_warnings=True
    )
    if runas:
        # Warn users about the deprecation
        ret.setdefault('warnings', []).append(
            'The \'runas\' argument is being deprecated in favor of \'user\', '
            'please update your state files.'
        )
    if user is not None and runas is not None:
        # user wins over runas but let warn about the deprecation.
        ret.setdefault('warnings', []).append(
            'Passed both the \'runas\' and \'user\' arguments. Please don\'t. '
            '\'runas\' is being ignored in favor of \'user\'.'
        )
        runas = None
    elif runas is not None:
        # Support old runas usage
        user = runas
        runas = None

    try:
        call = __salt__['npm.install'](dir=name, runas=user, pkg=None)
    except (CommandNotFoundError, CommandExecutionError) as err:
        ret['result'] = False
        ret['comment'] = 'Error Bootstrapping {0!r}: {1}'.format(name, err)
        return ret

    if not call:
        ret['result'] = True
        ret['comment'] = 'Directory is already bootstrapped'
        return ret

    # npm.install will return a string if it can't parse a JSON result
    if isinstance(call, str):
        ret['result'] = False
        ret['comment'] = 'Could not bootstrap directory'
    else:
        ret['result'] = True
        ret['changes'] = {name: 'Bootstrapped'}
        ret['comment'] = 'Directory was successfully bootstrapped'

    return ret
