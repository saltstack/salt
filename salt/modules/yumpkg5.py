# -*- coding: utf-8 -*-
'''
Support for YUM
'''

# Import python libs
import collections
import copy
import logging
import re

# Import salt libs
import salt.utils
from salt.utils import namespaced_function as _namespaced_function
from salt.modules.yumpkg import (mod_repo, _parse_repo_file, list_repos,
                                 get_repo, expand_repo_def, del_repo)

# Import libs required by functions imported from yumpkg
# DO NOT REMOVE THESE, ON PAIN OF DEATH
import os

log = logging.getLogger(__name__)

# This is imported in salt.modules.pkg_resource._parse_pkg_meta. Don't change
# it without considering its impact there.
__QUERYFORMAT = '%{NAME}_|-%{VERSION}_|-%{RELEASE}_|-%{ARCH}'

__SUFFIX_NOT_NEEDED = ('x86_64', 'noarch')

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Confine this module to yum based systems
    '''
    # Work only on RHEL/Fedora based distros with python 2.5 and below
    try:
        os_grain = __grains__['os']
        os_family = __grains__['os_family']
        os_major_version = int(__grains__['osrelease'].split('.')[0])
    except Exception:
        return False

    valid = False
    # Fedora <= 10 need to use this module
    if os_grain == 'Fedora' and os_major_version < 11:
        valid = True
    # XCP == 1.x uses a CentOS 5 base
    elif os_grain == 'XCP':
        if os_major_version == 1:
            valid = True
    # XenServer 6 and earlier uses a CentOS 5 base
    elif os_grain == 'XenServer':
        if os_major_version <= 6:
            valid = True
    else:
        # RHEL <= 5 and all variants need to use this module
        if os_family == 'RedHat' and os_major_version <= 5:
            valid = True
    if valid:
        global mod_repo, _parse_repo_file, list_repos, get_repo
        global expand_repo_def, del_repo
        mod_repo = _namespaced_function(mod_repo, globals())
        _parse_repo_file = _namespaced_function(_parse_repo_file, globals())
        list_repos = _namespaced_function(list_repos, globals())
        get_repo = _namespaced_function(get_repo, globals())
        expand_repo_def = _namespaced_function(expand_repo_def, globals())
        del_repo = _namespaced_function(del_repo, globals())
        return 'pkg'
    return False


# This is imported in salt.modules.pkg_resource._parse_pkg_meta. Don't change
# it without considering its impact there.
def _parse_pkginfo(line):
    '''
    A small helper to parse package information; returns a namedtuple
    '''
    # Need to reimport `collections` as this function is re-namespaced into
    # other modules
    import collections

    pkginfo = collections.namedtuple('PkgInfo', ('name', 'shortname',
                                                 'version', 'arch'))

    try:
        name, pkgver, rel, arch = line.split('_|-')
    # Handle unpack errors (should never happen with the queryformat we are
    # using, but can't hurt to be careful).
    except ValueError:
        return None

    shortname = name
    # Support 32-bit packages on x86_64 systems
    if __grains__.get('cpuarch') in __SUFFIX_NOT_NEEDED \
            and arch not in __SUFFIX_NOT_NEEDED:
        name += '.{0}'.format(arch)
    if rel:
        pkgver += '-{0}'.format(rel)

    return pkginfo(name, shortname, pkgver, arch)


def _repoquery(repoquery_args):
    '''
    Runs a repoquery command and returns a list of namedtuples
    '''
    ret = []
    cmd = 'repoquery {0}'.format(repoquery_args)
    output = __salt__['cmd.run_all'](cmd).get('stdout', '').splitlines()
    for line in output:
        pkginfo = _parse_pkginfo(line)
        if pkginfo is not None:
            ret.append(pkginfo)
    return ret


def _get_repo_options(**kwargs):
    '''
    Returns a string of '--enablerepo' and '--disablerepo' options to be used
    in the yum command, based on the kwargs.
    '''
    # Get repo options from the kwargs
    fromrepo = kwargs.get('fromrepo', '')
    repo = kwargs.get('repo', '')
    disablerepo = kwargs.get('disablerepo', '')
    enablerepo = kwargs.get('enablerepo', '')

    # Support old 'repo' argument
    if repo and not fromrepo:
        fromrepo = repo

    repo_arg = ''
    if fromrepo:
        log.info('Restricting to repo {0!r}'.format(fromrepo))
        repo_arg = ('--disablerepo={0!r} --enablerepo={1!r}'
                    .format('*', fromrepo))
    else:
        repo_arg = ''
        if disablerepo:
            log.info('Disabling repo {0!r}'.format(disablerepo))
            repo_arg += '--disablerepo={0!r} '.format(disablerepo)
        if enablerepo:
            log.info('Enabling repo {0!r}'.format(enablerepo))
            repo_arg += '--enablerepo={0!r} '.format(enablerepo)
    return repo_arg


def _pkg_arch(name):
    '''
    Returns a 2-tuple of the name and arch parts of the passed string. Note
    that packages that are for the system architecture should not have the
    architecture specified in the passed string.
    '''
    # TODO: Fix __grains__ availability in provider overrides
    try:
        pkgname, pkgarch = name.rsplit('.', 1)
    except ValueError:
        return name, __grains__['cpuarch']
    if pkgarch in __SUFFIX_NOT_NEEDED:
        pkgname = name
    return pkgname, pkgarch


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    A specific repo can be requested using the ``fromrepo`` keyword argument.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package name> fromrepo=epel-testing
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    refresh = salt.utils.is_true(kwargs.pop('refresh', True))
    # FIXME: do stricter argument checking that somehow takes
    # _get_repo_options() into account

    if len(names) == 0:
        return ''
    ret = {}
    namearch_map = {}
    # Initialize the return dict with empty strings, and populate the namearch
    # dict
    for name in names:
        ret[name] = ''
        pkgname, pkgarch = _pkg_arch(name)
        namearch_map.setdefault(name, {})['name'] = pkgname
        namearch_map[name]['arch'] = pkgarch

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db()

    # Get updates for specified package(s)
    repo_arg = _get_repo_options(**kwargs)
    updates = _repoquery(
        '{0} --pkgnarrow=available --queryformat {1!r} '
        '{2}'.format(
            repo_arg,
            __QUERYFORMAT,
            ' '.join([namearch_map[x]['name'] for x in names])
        )
    )

    for name in names:
        for pkg in (x for x in updates
                    if x.shortname == namearch_map[name]['name']):
            if (all(x in __SUFFIX_NOT_NEEDED
                    for x in (namearch_map[name]['arch'], pkg.arch))
                    or namearch_map[name]['arch'] == pkg.arch):
                ret[name] = pkg.version

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = latest_version


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    return latest_version(name) != ''


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


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    # 'removed' not yet implemented or not applicable
    if salt.utils.is_true(kwargs.get('removed')):
        return {}

    if 'pkg.list_pkgs' in __context__:
        if versions_as_list:
            return __context__['pkg.list_pkgs']
        else:
            ret = copy.deepcopy(__context__['pkg.list_pkgs'])
            __salt__['pkg_resource.stringify'](ret)
            return ret

    ret = {}
    cmd = 'rpm -qa --queryformat "{0}\n"'.format(__QUERYFORMAT)
    for line in __salt__['cmd.run'](cmd).splitlines():
        pkginfo = _parse_pkginfo(line)
        if pkginfo is None:
            continue
        __salt__['pkg_resource.add_pkg'](ret, pkginfo.name, pkginfo.version)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def list_upgrades(refresh=True, **kwargs):
    '''
    Check whether or not an upgrade is available for all packages

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    repo_arg = _get_repo_options(**kwargs)
    updates = _repoquery('{0} --all --pkgnarrow=updates --queryformat '
                         '"{1}"'.format(repo_arg, __QUERYFORMAT))
    return dict([(x.name, x.version) for x in updates])


def check_db(*names, **kwargs):
    '''
    .. versionadded:: 0.17.0

    Returns a dict containing the following information for each specified
    package:

    1. A key ``found``, which will be a boolean value denoting if a match was
       found in the package database.
    2. If ``found`` is ``False``, then a second key called ``suggestions`` will
       be present, which will contain a list of possible matches.

    The ``fromrepo``, ``enablerepo``, and ``disablerepo`` arguments are
    supported, as used in pkg states.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.check_db <package1> <package2> <package3>
        salt '*' pkg.check_db <package1> <package2> <package3> fromrepo=epel-testing
    '''
    repo_arg = _get_repo_options(**kwargs)
    deplist_base = 'yum {0} deplist --quiet'.format(repo_arg) + ' {0!r}'
    repoquery_base = ('{0} -a --quiet --whatprovides --queryformat '
                      '{1!r}'.format(repo_arg, __QUERYFORMAT))

    ret = {}
    for name in names:
        ret.setdefault(name, {})['found'] = bool(
            __salt__['cmd.run'](deplist_base.format(name))
        )
        if ret[name]['found'] is False:
            repoquery_cmd = repoquery_base + ' {0!r}'.format(name)
            provides = set([x.name for x in _repoquery(repoquery_cmd)])
            if provides:
                for pkg in provides:
                    ret[name]['suggestions'] = list(provides)
            else:
                ret[name]['suggestions'] = []
    return ret


def refresh_db():
    '''
    Since yum refreshes the database automatically, this runs a yum clean,
    so that the next yum operation will have a clean database

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    cmd = 'yum -q clean dbcache'
    __salt__['cmd.retcode'](cmd)
    return True


def install(name=None,
            refresh=False,
            fromrepo=None,
            skip_verify=False,
            pkgs=None,
            sources=None,
            **kwargs):
    '''
    Install the passed package(s), add refresh=True to clean the yum database
    before package is installed.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either "pkgs" or "sources" is passed. Additionally, please
        note that this option can only be used to install packages from a
        software repository. To install a package file manually, use the
        "sources" option.

        32-bit packages can be installed on 64-bit systems by appending the
        architecture designation (``.i686``, ``.i586``, etc.) to the end of the
        package name.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    refresh
        Whether or not to update the yum database before executing.

    skip_verify
        Skip the GPG verification check (e.g., ``--nogpgcheck``)

    version
        Install a specific version of the package, e.g. 1.2.3-4.el5. Ignored
        if "pkgs" or "sources" is passed.


    Repository Options:

    fromrepo
        Specify a package repository (or repositories) from which to install.
        (e.g., ``yum --disablerepo='*' --enablerepo='somerepo'``)

    enablerepo (ignored if ``fromrepo`` is specified)
        Specify a disabled package repository (or repositories) to enable.
        (e.g., ``yum --enablerepo='somerepo'``)

    disablerepo (ignored if ``fromrepo`` is specified)
        Specify an enabled package repository (or repositories) to disable.
        (e.g., ``yum --disablerepo='somerepo'``)


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list. A specific version number can be specified
        by using a single-element dict representing the package and its
        version.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-4.el5"}]'

    sources
        A list of RPM packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.rpm"}, {"bar": "salt://bar.rpm"}]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources,
                                                                  **kwargs)
    if pkg_params is None or len(pkg_params) == 0:
        return {}

    version_num = kwargs.get('version')
    if version_num:
        if pkgs is None and sources is None:
            # Allow "version" to work for single package target
            pkg_params = {name: version_num}
        else:
            log.warning('"version" parameter will be ignored for multiple '
                        'package targets')

    repo_arg = _get_repo_options(fromrepo=fromrepo, **kwargs)

    old = list_pkgs()
    downgrade = []
    if pkg_type == 'repository':
        targets = []
        for pkgname, version_num in pkg_params.iteritems():
            if version_num is None:
                targets.append(pkgname)
            else:
                cver = old.get(pkgname, '')
                if __grains__.get('cpuarch', '') == 'x86_64':
                    try:
                        arch = re.search(r'(\.i\d86)$', pkgname).group(1)
                    except AttributeError:
                        arch = ''
                    else:
                        # Remove arch from pkgname
                        pkgname = pkgname[:-len(arch)]
                else:
                    arch = ''
                pkgstr = '"{0}-{1}{2}"'.format(pkgname, version_num, arch)
                if not cver or salt.utils.compare_versions(ver1=version_num,
                                                           oper='>=',
                                                           ver2=cver):
                    targets.append(pkgstr)
                else:
                    downgrade.append(pkgstr)
    else:
        targets = pkg_params

    if targets:
        cmd = 'yum -y {repo} {gpgcheck} install {pkg}'.format(
            repo=repo_arg,
            gpgcheck='--nogpgcheck' if skip_verify else '',
            pkg=' '.join(targets),
        )
        __salt__['cmd.run_all'](cmd)

    if downgrade:
        cmd = 'yum -y {repo} {gpgcheck} downgrade {pkg}'.format(
            repo=repo_arg,
            gpgcheck='--nogpgcheck' if skip_verify else '',
            pkg=' '.join(downgrade),
        )
        __salt__['cmd.run_all'](cmd)

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def upgrade(refresh=True):
    '''
    Run a full system upgrade, a yum upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''
    if salt.utils.is_true(refresh):
        refresh_db()
    old = list_pkgs()
    cmd = 'yum -q -y upgrade'
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def remove(name=None, pkgs=None, **kwargs):
    '''
    Remove packages with ``yum -q -y remove``.

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
    pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    cmd = 'yum -q -y remove "{0}"'.format('" "'.join(targets))
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def purge(name=None, pkgs=None, **kwargs):
    '''
    Package purges are not supported by yum, this function is identical to
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
