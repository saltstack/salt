# -*- coding: utf-8 -*-
'''
Package support for OpenBSD
'''
from __future__ import absolute_import

# Import python libs
import copy
import re
import logging

# Import Salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, MinionError

log = logging.getLogger(__name__)


__PKG_RE = re.compile('^((?:[^-]+|-(?![0-9]))+)-([0-9][^-]*)(?:-(.*))?$')

# Define the module's virtual name
__virtualname__ = 'pkg'

# XXX need a way of setting PKG_PATH instead of inheriting from the environment


def __virtual__():
    '''
    Set the virtual pkg module if the os is OpenBSD
    '''
    if __grains__['os'] == 'OpenBSD':
        return __virtualname__
    return (False, 'The openbsdpkg execution module cannot be loaded: '
            'only available on OpenBSD systems.')


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    # not yet implemented or not applicable
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
    cmd = 'pkg_info -q -a'
    out = __salt__['cmd.run_stdout'](cmd, output_loglevel='trace')
    for line in out.splitlines():
        try:
            pkgname, pkgver, flavor = __PKG_RE.match(line).groups()
        except AttributeError:
            continue
        pkgname += '--{0}'.format(flavor) if flavor else ''
        __salt__['pkg_resource.add_pkg'](ret, pkgname, pkgver)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def latest_version(*names, **kwargs):
    '''
    The available version of the package in the repository

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
    '''
    kwargs.pop('refresh', True)

    pkgs = list_pkgs()
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ''

    stems = [x.split('--')[0] for x in names]
    cmd = 'pkg_info -q -I {0}'.format(' '.join(stems))
    out = __salt__['cmd.run_stdout'](cmd, python_shell=False, output_loglevel='trace')
    for line in out.splitlines():
        try:
            pkgname, pkgver, flavor = __PKG_RE.match(line).groups()
        except AttributeError:
            continue
        pkgname += '--{0}'.format(flavor) if flavor else ''
        cur = pkgs.get(pkgname, '')
        if not cur or salt.utils.compare_versions(ver1=cur,
                                                  oper='<',
                                                  ver2=pkgver):
            ret[pkgname] = pkgver

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = salt.utils.alias_function(latest_version, 'available_version')


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def install(name=None, pkgs=None, sources=None, **kwargs):
    '''
    Install the passed package

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example, Install one package:

    .. code-block:: bash

        salt '*' pkg.install <package name>

    CLI Example, Install more than one package:

    .. code-block:: bash

        salt '*' pkg.install pkgs='["<package name>", "<package name>"]'

    CLI Example, Install more than one package from a alternate source (e.g. salt file-server, HTTP, FTP, local filesystem):

    .. code-block:: bash

        salt '*' pkg.install sources='[{"<pkg name>": "salt://pkgs/<pkg filename>"}]'
    '''
    try:
        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    old = list_pkgs()
    errors = []
    for pkg in pkg_params:
        if pkg_type == 'repository':
            stem, flavor = (pkg.split('--') + [''])[:2]
            pkg = '--'.join((stem, flavor))
        cmd = 'pkg_add -x -I {0}'.format(pkg)
        out = __salt__['cmd.run_all'](
            cmd,
            python_shell=False,
            output_loglevel='trace'
        )
        if out['retcode'] != 0 and out['stderr']:
            errors.append(out['stderr'])

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            'Problem encountered installing package(s)',
            info={'errors': errors, 'changes': ret}
        )

    return ret


def remove(name=None, pkgs=None, **kwargs):
    '''
    Remove a single package with pkg_delete

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
    try:
        pkg_params = [x.split('--')[0] for x in
                      __salt__['pkg_resource.parse_targets'](name, pkgs)[0]]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}

    cmd = 'pkg_delete -xD dependencies {0}'.format(' '.join(targets))

    out = __salt__['cmd.run_all'](
        cmd,
        python_shell=False,
        output_loglevel='trace'
    )
    if out['retcode'] != 0 and out['stderr']:
        errors = [out['stderr']]
    else:
        errors = []

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            'Problem encountered removing package(s)',
            info={'errors': errors, 'changes': ret}
        )

    return ret


def purge(name=None, pkgs=None, **kwargs):
    '''
    Package purges are not supported, this function is identical to
    ``remove()``.

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

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    return remove(name=name, pkgs=pkgs)
