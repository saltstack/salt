'''
Support for YUM
'''

# Import python libs
import logging
import collections

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Confine this module to yum based systems
    '''
    # Work only on RHEL/Fedora based distros with python 2.6 or greater
    try:
        os_grain = __grains__['os']
        os_family = __grains__['os_family']
        os_major_version = int(__grains__['osrelease'].split('.')[0])
    except Exception:
        return False

    # Fedora <= 10 need to use this module
    if os_grain == 'Fedora' and os_major_version < 11:
        return 'pkg'
    else:
        # RHEL <= 5 and all variants need to use this module
        if os_family == 'RedHat' and os_major_version <= 5:
            return 'pkg'
    return False


def _parse_yum(arg):
    '''
    A small helper to parse yum output; returns a list of namedtuples
    '''
    cmd = 'yum -q {0}'.format(arg)
    out = __salt__['cmd.run_stdout'](cmd)
    yum_out = collections.namedtuple('YumOut', ('name', 'version', 'status'))

    results = []

    for line in out.splitlines():
        if not line.startswith('Loaded plugin'):
            line = line.split()
            if len(line) == 3:
                namearchstr, pkgver, pkgstatus = line
                pkgname = namearchstr.rpartition('.')[0]
                results.append(yum_out(pkgname, pkgver, pkgstatus))
    return results


def _list_removed(old, new):
    '''
    List the packages which have been removed between the two package objects
    '''
    # Force input to be a list so below loop works
    if not isinstance(old, list):
        old = [old]
    if not isinstance(new, list):
        new = [new]
    pkgs = []
    for pkg in old:
        if pkg not in new:
            pkgs.append(pkg)
    return pkgs


def available_version(*names):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example::

        salt '*' pkg.available_version <package name>
        salt '*' pkg.available_version <package1> <package2> <package3> ...
    '''
    if len(names) == 0:
        return ''
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ''
    # Get updates for specified package(s)
    updates = _parse_yum('list available {0}'.format(' '.join(names)))
    for pkg in updates:
        ret[pkg.name] = pkg.version
    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return available_version(name) != ''


def version(*names):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example::

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    if len(names) == 0:
        return ''
    ret = {}
    pkgs = list_pkgs()
    for name in names:
        ret[name] = pkgs.get(name, '')
    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


def list_pkgs():
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    ret = {}
    cmd = 'rpm -qa --queryformat "%{NAME}_|-%{VERSION}_|-%{RELEASE}\n"'
    for line in __salt__['cmd.run'](cmd).splitlines():
        name, version, rel = line.split('_|-')
        pkgver = version
        if rel:
            pkgver += '-{0}'.format(rel)
        __salt__['pkg_resource.add_pkg'](ret, name, pkgver)
    __salt__['pkg_resource.sort_pkglist'](ret)
    return ret


def list_upgrades(refresh=True):
    '''
    Check whether or not an upgrade is available for all packages

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    # Catch both boolean input from state and string input from CLI
    if refresh is True or str(refresh).lower() == 'true':
        refresh_db()
    out = _parse_yum('check-update')
    return dict([(i.name, i.version) for i in out])


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
            salt '*' pkg.install sources='[{"foo": "salt://foo.rpm"},{"bar": "salt://bar.rpm"}]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    '''
    # Catch both boolean input from state and string input from CLI
    if refresh is True or str(refresh).lower() == 'true':
        refresh_db()

    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources)
    if pkg_params is None or len(pkg_params) == 0:
        return {}

    # Get repo options from the kwargs
    disablerepo = kwargs.get('disablerepo', '')
    enablerepo = kwargs.get('enablerepo', '')
    repo = kwargs.get('repo', '')

    version = kwargs.get('version')
    if version:
        if pkgs is None and sources is None:
            # Allow "version" to work for single package target
            pkg_params = {name: version}
        else:
            log.warning('"version" parameter will be ignored for muliple '
                        'package targets')

    # Support old "repo" argument
    if not fromrepo and repo:
        fromrepo = repo

    if fromrepo:
        log.info('Restricting install to repo "{0}"'.format(fromrepo))
        repo_arg = '--disablerepo="*" --enablerepo="{0}"'.format(fromrepo)
    else:
        repo_arg = ''
        if disablerepo:
            log.info('Disabling repo "{0}"'.format(disablerepo))
            repo_arg += '--disablerepo="{0}" '.format(disablerepo)
        if enablerepo:
            log.info('Enabling repo "{0}"'.format(enablerepo))
            repo_arg += '--enablerepo="{0}" '.format(enablerepo)

    old = list_pkgs()
    downgrade = []
    if pkg_type == 'repository':
        targets = []
        for param, version in pkg_params.iteritems():
            if version is None:
                targets.append(param)
            else:
                pkgstr = '"{0}-{1}"'.format(param, version)
                cver = old.get(param, '')
                if not cver or __salt__['pkg.compare'](pkg1=version,
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
    # Catch both boolean input from state and string input from CLI
    if refresh is True or str(refresh).lower() == 'true':
        refresh_db()
    old = list_pkgs()
    cmd = 'yum -q -y upgrade'
    __salt__['cmd.retcode'](cmd)
    new = list_pkgs()
    pkgs = {}
    for npkg in new:
        if npkg in old:
            if old[npkg] == new[npkg]:
                # no change in the package
                continue
            else:
                # the package was here before and the version has changed
                pkgs[npkg] = {'old': old[npkg],
                              'new': new[npkg]}
        else:
            # the package is freshly installed
            pkgs[npkg] = {'old': '',
                          'new': new[npkg]}
    return pkgs


def remove(pkg, **kwargs):
    '''
    Remove a single package with yum remove

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    old = list_pkgs()
    cmd = 'yum -q -y remove ' + pkg
    __salt__['cmd.retcode'](cmd)
    new = list_pkgs()
    return _list_removed(old, new)


def purge(pkg, **kwargs):
    '''
    Yum does not have a purge, this function calls remove

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    return remove(pkg)


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
