'''
Support for YUM
'''

# Import python libs
import copy
import logging
import collections

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

__QUERYFORMAT = '%{NAME}_|-%{VERSION}_|-%{RELEASE}_|-%{ARCH}'


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

    # Fedora <= 10 need to use this module
    if os_grain == 'Fedora' and os_major_version < 11:
        return 'pkg'
    # XCP == 1.x uses a CentOS 5 base
    elif os_grain == 'XCP':
        if os_major_version == 1:
            return 'pkg'
    # XenServer 6 and earlier uses a CentOS 5 base
    elif os_grain == 'XenServer':
        if os_major_version <= 6:
            return 'pkg'
    else:
        # RHEL <= 5 and all variants need to use this module
        if os_family == 'RedHat' and os_major_version <= 5:
            return 'pkg'
    return False


def _parse_pkginfo(line):
    '''
    A small helper to parse package information; returns a namedtuple
    '''
    pkginfo = collections.namedtuple('PkgInfo', ('name', 'version'))

    try:
        name, pkgver, rel, arch = line.split('_|-')
    # Handle unpack errors (should never happen with the queryformat we are
    # using, but can't hurt to be careful).
    except ValueError:
        return None

    # Support 32-bit packages on x86_64 systems
    if __grains__.get('cpuarch', '') == 'x86_64' and arch == 'i686':
        name += '.i686'
    if rel:
        pkgver += '-{0}'.format(rel)

    return pkginfo(name, pkgver)


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
        log.info('Restricting to repo "{0}"'.format(fromrepo))
        repo_arg = '--disablerepo="*" --enablerepo="{0}"'.format(fromrepo)
    else:
        repo_arg = ''
        if disablerepo:
            log.info('Disabling repo "{0}"'.format(disablerepo))
            repo_arg += '--disablerepo="{0}" '.format(disablerepo)
        if enablerepo:
            log.info('Enabling repo "{0}"'.format(enablerepo))
            repo_arg += '--enablerepo="{0}" '.format(enablerepo)
    return repo_arg


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    A specific repo can be requested using the ``fromrepo`` keyword argument.

    CLI Example::

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package name> fromrepo=epel-testing
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    if len(names) == 0:
        return ''
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ''

    # Get updates for specified package(s)
    repo_arg = _get_repo_options(**kwargs)
    updates = _repoquery('{0} --pkgnarrow=available --queryformat "{1}" '
                         '{2}'.format(repo_arg,
                                      __QUERYFORMAT,
                                      ' '.join(names)))
    for pkg in updates:
        ret[pkg.name] = pkg.version
    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = latest_version


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return latest_version(name) != ''


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example::

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example::

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

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    repo_arg = _get_repo_options(**kwargs)
    updates = _repoquery('{0} --all --pkgnarrow=updates --queryformat '
                         '"{1}"'.format(repo_arg, __QUERYFORMAT))
    return dict([(x.name, x.version) for x in updates])


def refresh_db():
    '''
    Since yum refreshes the database automatically, this runs a yum clean,
    so that the next yum operation will have a clean database

    CLI Example::

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

        32-bit packages can be installed on 64-bit systems by appending
        ``.i686`` to the end of the package name.

        CLI Example::
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

        CLI Examples::
            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-4.el5"}]'

    sources
        A list of RPM packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example::
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
                if __grains__.get('cpuarch', '') == 'x86_64' \
                        and pkgname.endswith('.i686'):
                    # Remove '.i686' from pkgname
                    pkgname = pkgname[:-5]
                    arch = '.i686'
                else:
                    arch = ''
                pkgstr = '"{0}-{1}{2}"'.format(pkgname, version_num, arch)
                if not cver or __salt__['pkg.compare'](pkg1=version_num,
                                                       oper='>=',
                                                       pkg2=cver):
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

    CLI Example::

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


    Returns a dict containing the changes.

    CLI Example::

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


    Returns a dict containing the changes.

    CLI Example::

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    return remove(name=name, pkgs=pkgs)


def perform_cmp(pkg1='', pkg2=''):
    '''
    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    CLI Example::

        salt '*' pkg.perform_cmp '0.2.4-0' '0.2.4.1-0'
        salt '*' pkg.perform_cmp pkg1='0.2.4-0' pkg2='0.2.4.1-0'
    '''
    return __salt__['pkg_resource.perform_cmp'](pkg1=pkg1, pkg2=pkg2)


def compare(pkg1='', oper='==', pkg2=''):
    '''
    Compare two version strings.

    CLI Example::

        salt '*' pkg.compare '0.2.4-0' '<' '0.2.4.1-0'
        salt '*' pkg.compare pkg1='0.2.4-0' oper='<' pkg2='0.2.4.1-0'
    '''
    return __salt__['pkg_resource.compare'](pkg1=pkg1, oper=oper, pkg2=pkg2)
