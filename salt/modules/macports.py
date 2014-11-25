# -*- coding: utf-8 -*-
'''
Support for MacPorts under Mac OSX.

This module has some caveats.

1. Updating the database of available ports is quite resource-intensive.
However, `refresh=True` is the default for all operations that need an
up-to-date copy of available ports.  Consider `refresh=False` when you are
sure no db update is needed.

2. In some cases MacPorts doesn't always realize when another copy of itself
is running and will gleefully tromp all over the available ports database.
This makes MacPorts behave in undefined ways until a fresh complete
copy is retrieved.

Because of 1 and 2 it is possible to get the salt-minion into a state where
`salt mac-machine pkg./something/` won't want to return.  Use

`salt-run jobs.active`

on the master to check for potentially long-running calls to `port`.

Finally, ports database updates are always handled with `port selfupdate`
as opposed to `port sync`.  This makes sense in the MacPorts user commmunity
but may confuse experienced Linux admins as Linux package managers
don't upgrade the packaging software when doing a package database update.
In other words `salt mac-machine pkg.refresh_db` is more like
`apt-get update; apt-get upgrade dpkg apt-get` than simply `apt-get update`.

'''
from __future__ import absolute_import

# Import python libs
import copy
import logging
import re

# Import salt libs
import salt.utils
from salt.exceptions import (
    CommandExecutionError
)

log = logging.getLogger(__name__)

LIST_ACTIVE_ONLY = True
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Confine this module to Mac OS with MacPorts.
    '''

    if salt.utils.which('port') and __grains__['os'] == 'MacOS':
        return __virtualname__
    return False


def _list(query=''):
    ret = {}
    cmd = 'port list {0}'.format(query)
    call = __salt__['cmd.run_all'](cmd, output_loglevel='trace')

    if call['retcode'] != 0:
        comment = ''
        if 'stderr' in call:
            comment += call['stderr']
        if 'stdout' in call:
            comment += call['stdout']
        raise CommandExecutionError(
            '{0}'.format(comment)
        )
    else:
        out = call['stdout']

    for line in out.splitlines():
        try:
            name, version_num, category = re.split(r'\s+', line.lstrip())[0:3]
            version_num = version_num[1:]
        except ValueError:
            continue
        ret[name] = version_num

    return ret


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    # 'removed', 'purge_desired' not yet implemented or not applicable
    if any([salt.utils.is_true(kwargs.get(x))
            for x in ('removed', 'purge_desired')]):
        return {}

    if 'pkg.list_pkgs' in __context__:
        if versions_as_list:
            return __context__['pkg.list_pkgs']
        else:
            ret = copy.deepcopy(__context__['pkg.list_pkgs'])
            __salt__['pkg_resource.stringify'](ret)
            return ret

    ret = {}
    cmd = ['port', 'installed']
    out = __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)
    for line in out.splitlines():
        try:
            name, version_num, active = re.split(r'\s+', line.lstrip())[0:3]
            version_num = version_num[1:]
        except ValueError:
            continue
        if not LIST_ACTIVE_ONLY or active == '(active)':
            __salt__['pkg_resource.add_pkg'](ret, name, version_num)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3>
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation

    Options:

    refresh
        Update ports with ``port selfupdate``

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3>
    '''

    if salt.utils.is_true(kwargs.get('refresh', True)):
        refresh_db()

    available = _list(' '.join(names)) or {}
    installed = __salt__['pkg.list_pkgs']() or {}

    ret = {}

    for k, v in available.items():
        if k not in installed or salt.utils.compare_versions(ver1=installed[k], oper='<', ver2=v):
            ret[k] = v
        else:
            ret[k] = ''

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]

    return ret

# available_version is being deprecated
available_version = latest_version


def remove(name=None, pkgs=None, **kwargs):
    '''
    Removes packages with ``port uninstall``.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    pkg_params = __salt__['pkg_resource.parse_targets'](name,
                                                        pkgs,
                                                        **kwargs)[0]
    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    cmd = ['port', 'uninstall']
    cmd.extend(targets)
    __salt__['cmd.run_all'](cmd, output_loglevel='trace', python_shell=False)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def install(name=None, refresh=False, pkgs=None, **kwargs):
    '''
    Install the passed package(s) with ``port install``

    name
        The name of the formula to be installed. Note that this parameter is
        ignored if "pkgs" is passed.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    version
        Specify a version to pkg to install. Ignored if pkgs is specified.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>
            salt '*' pkg.install git-core version='1.8.5.5'

    variant
        Specify a variant to pkg to install. Ignored if pkgs is specified.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>
            salt '*' pkg.install git-core version='1.8.5.5' variant='+credential_osxkeychain+doc+pcre'

    Multiple Package Installation Options:

    pkgs
        A list of formulas to install. Must be passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo","bar"]'
            salt '*' pkg.install pkgs='["foo@1.2","bar"]'
            salt '*' pkg.install pkgs='["foo@1.2+ssl","bar@2.3"]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install 'package package package'
    '''
    pkg_params, pkg_type = \
        __salt__['pkg_resource.parse_targets'](name,
                                               pkgs,
                                               {})

    if salt.utils.is_true(refresh):
        refresh_db()

    # Handle version kwarg for a single package target
    if pkgs is None:
        version_num = kwargs.get('version')
        variant_spec = kwargs.get('variant')
        spec = None

        if version_num:
            spec = (spec or '') + '@' + version_num

        if variant_spec:
            spec = (spec or '') + variant_spec

        pkg_params = {name: spec}

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    formulas_array = []
    for pname, pparams in pkg_params.items():
        formulas_array.append(pname + (pparams or ''))

    old = list_pkgs()
    cmd = ['port', 'install']
    cmd.extend(formulas_array)

    __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def list_upgrades(refresh=True):
    '''
    Check whether or not an upgrade is available for all packages

    Options:

    refresh
        Update ports with ``port selfupdate``

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''

    if refresh:
        refresh_db()
    return _list('outdated')


def upgrade_available(pkg, refresh=True):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    return pkg in list_upgrades(refresh=refresh)


def refresh_db():
    '''
    Update ports with ``port selfupdate``
    '''
    call = __salt__['cmd.run_all']('port selfupdate', output_loglevel='trace')
    if call['retcode'] != 0:
        comment = ''
        if 'stderr' in call:
            comment += call['stderr']

        raise CommandExecutionError(
            '{0}'.format(comment)
        )


def upgrade(refresh=True):  # pylint: disable=W0613
    '''
    Run a full upgrade using MacPorts 'port upgrade outdated'

    Options:

    refresh
        Update ports with ``port selfupdate``

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''
    ret = {'changes': {},
           'result': True,
           'comment': '',
           }

    if refresh:
        refresh_db()

    old = list_pkgs()
    cmd = ['port', 'upgrade', 'outdated']

    __salt__['cmd.run_all'](cmd, output_loglevel='trace', python_shell=False)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)
