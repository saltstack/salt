# -*- coding: utf-8 -*-
'''
Package support for pkgin based systems, inspired from freebsdpkg module
'''

# Import python libs
import os
import re
import logging

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.exceptions import CommandExecutionError, MinionError

VERSION_MATCH = re.compile(r'pkgin(?:[\s]+)([\d.]+)(?:[\s]+)(?:.*)')
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pkg'


@decorators.memoize
def _check_pkgin():
    '''
    Looks to see if pkgin is present on the system, return full path
    '''
    ppath = salt.utils.which('pkgin')
    if ppath is None:
        # pkgin was not found in $PATH, try to find it via LOCALBASE
        localbase = __salt__['cmd.run'](
            'pkg_info -Q LOCALBASE pkgin',
            output_loglevel='debug'
        )
        if localbase is not None:
            ppath = '{0}/bin/pkgin'.format(localbase)
            if not os.path.exists(ppath):
                return None

    return ppath


@decorators.memoize
def _supports_regex():
    '''
    Get the pkgin version
    '''
    ppath = _check_pkgin()
    version_string = __salt__['cmd.run'](
        '{0} -v'.format(ppath), output_loglevel='debug'
    )
    if version_string is None:
        # Dunno why it would, but...
        return False

    version_match = VERSION_MATCH.search(version_string)
    if not version_match:
        return False

    return tuple([int(i) for i in version_match.group(1).split('.')]) > (0, 5)


def __virtual__():
    '''
    Set the virtual pkg module if the os is supported by pkgin
    '''
    supported = ['NetBSD', 'SunOS', 'DragonFly', 'Minix', 'Darwin', 'SmartOS']

    if __grains__['os'] in supported and _check_pkgin():
        return __virtualname__
    return False


def _splitpkg(name):
    # name is in the format foobar-1.0nb1, already space-splitted
    if name[0].isalnum() and name != 'No':  # avoid < > = and 'No result'
        return name.rsplit('-', 1)


def search(pkg_name):
    '''
    Searches for an exact match using pkgin ^package$

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.search 'mysql-server'
    '''

    pkglist = {}
    pkgin = _check_pkgin()
    if not pkgin:
        return pkglist

    if _supports_regex():
        pkg_name = '^{0}$'.format(pkg_name)

    out = __salt__['cmd.run'](
        '{0} se {1}'.format(pkgin, pkg_name),
        output_loglevel='debug'
    )
    for line in out.splitlines():
        if line:
            match = _splitpkg(line.split()[0])
            if match:
                pkglist[match[0]] = match[1]

    return pkglist


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> ...
    '''

    refresh = salt.utils.is_true(kwargs.pop('refresh', True))

    pkglist = {}
    pkgin = _check_pkgin()
    if not pkgin:
        return pkglist

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db()

    for name in names:
        if _supports_regex():
            name = '^{0}$'.format(name)
        out = __salt__['cmd.run'](
            '{0} se {1}'.format(pkgin, name),
            output_loglevel='debug'
        )
        for line in out.splitlines():
            p = line.split()  # pkgname-version status
            if p and p[0] in ('=:', '<:', '>:'):
                # These are explanation comments
                continue
            elif p:
                s = _splitpkg(p[0])
                if s:
                    if len(p) > 1 and p[1] == '<':
                        pkglist[s[0]] = s[1]
                    else:
                        pkglist[s[0]] = ''

    if len(names) == 1 and pkglist:
        return pkglist[names[0]]

    return pkglist


# available_version is being deprecated
available_version = latest_version


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


def refresh_db():
    '''
    Use pkg update to get latest pkg_summary

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''

    pkgin = _check_pkgin()

    if pkgin:
        __salt__['cmd.run']('{0} up'.format(pkgin), output_loglevel='debug')

    return {}


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

    pkgin = _check_pkgin()
    if pkgin:
        pkg_command = '{0} ls'.format(pkgin)
    else:
        pkg_command = 'pkg_info'

    ret = {}

    out = __salt__['cmd.run'](pkg_command, output_loglevel='debug')
    for line in out.splitlines():
        if not line:
            continue
        pkg, ver = line.split(' ')[0].rsplit('-', 1)
        __salt__['pkg_resource.add_pkg'](ret, pkg, ver)

    __salt__['pkg_resource.sort_pkglist'](ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def install(name=None, refresh=False, fromrepo=None,
            pkgs=None, sources=None, **kwargs):
    '''
    Install the passed package

    name
        The name of the package to be installed.

    refresh
        Whether or not to refresh the package database before installing.

    fromrepo
        Specify a package repository to install from.


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo","bar"]'

    sources
        A list of packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.deb"},{"bar": "salt://bar.deb"}]'

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install <package name>
    '''
    try:
        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    # Support old "repo" argument
    repo = kwargs.get('repo', '')
    if not fromrepo and repo:
        fromrepo = repo

    if not pkg_params:
        return {}

    env = []
    args = []
    pkgin = _check_pkgin()
    if pkgin:
        cmd = pkgin
        if fromrepo:
            log.info('Setting PKG_REPOS={0}'.format(fromrepo))
            env.append(('PKG_REPOS', fromrepo))
    else:
        cmd = 'pkg_add'
        if fromrepo:
            log.info('Setting PKG_PATH={0}'.format(fromrepo))
            env.append(('PKG_PATH', fromrepo))

    if pkg_type == 'file':
        cmd = 'pkg_add'
    elif pkg_type == 'repository':
        if pkgin:
            if refresh:
                args.append('-f')  # update repo db
            args.extend(('-y', 'in'))  # Assume yes when asked

    args.extend(pkg_params)

    old = list_pkgs()
    __salt__['cmd.run'](
        '{0} {1}'.format(cmd, ' '.join(args)),
        env=env,
        output_loglevel='debug'
    )
    new = list_pkgs()

    rehash()
    return salt.utils.compare_dicts(old, new)


def upgrade():
    '''
    Run pkg upgrade, if pkgin used. Otherwise do nothing

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''

    pkgin = _check_pkgin()
    if not pkgin:
        # There is not easy way to upgrade packages with old package system
        return {}

    old = list_pkgs()
    __salt__['cmd.retcode']('{0} -y fug'.format(pkgin))
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def remove(name=None, pkgs=None, **kwargs):
    '''
    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a list containing the removed packages.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    try:
        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](
            name, pkgs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if not pkg_params:
        return {}

    old = list_pkgs()
    args = []

    for param in pkg_params:
        ver = old.get(param, [])
        if not ver:
            continue
        if isinstance(ver, list):
            args.extend(['{0}-{1}'.format(param, v) for v in ver])
        else:
            args.append('{0}-{1}'.format(param, ver))

    if not args:
        return {}

    for_remove = ' '.join(args)

    pkgin = _check_pkgin()
    if pkgin:
        cmd = '{0} -y remove {1}'.format(pkgin, for_remove)
    else:
        cmd = 'pkg_remove {0}'.format(for_remove)

    __salt__['cmd.run'](cmd, output_loglevel='debug')
    new = list_pkgs()

    return salt.utils.compare_dicts(old, new)


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


def rehash():
    '''
    Recomputes internal hash table for the PATH variable.
    Use whenever a new command is created during the current
    session.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.rehash
    '''
    shell = __salt__['cmd.run']('echo $SHELL', output_loglevel='debug')
    if shell.split('/')[-1] in ('csh', 'tcsh'):
        __salt__['cmd.run']('rehash', output_loglevel='debug')


def file_list(package):
    '''
    List the files that belong to a package.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list nginx
    '''
    ret = file_dict(package)
    files = []
    for pkg_files in ret['files'].values():
        files.extend(pkg_files)
    ret['files'] = files
    return ret


def file_dict(package):
    '''
    List the files that belong to a package.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list nginx
    '''
    errors = []
    files = {}
    files[package] = None

    cmd = 'pkg_info -qL {0}'.format(package)
    ret = __salt__['cmd.run_all'](cmd, output_loglevel='debug')

    for line in ret['stderr'].splitlines():
        errors.append(line)

    for line in ret['stdout'].splitlines():
        if line.startswith('/'):
            if files[package] is None:
                files[package] = [line]
            else:
                files[package].append(line)
        else:
            continue  # unexpected string

    print files
    return {'errors': errors, 'files': files}

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
