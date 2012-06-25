'''
Support for YUM
'''
import logging
from collections import namedtuple


logger = logging.getLogger(__name__)

def __virtual__():
    '''
    Confine this module to yum based systems
    '''
    # Return this for pkg on RHEL/Fedora based distros that do not ship with
    # python 2.6 or greater.
    dists = ('CentOS', 'Scientific', 'RedHat')
    if __grains__['os'] == 'Fedora':
        if int(__grains__['osrelease'].split('.')[0]) < 11:
            return 'pkg'
        else:
            return False
    else:
        if __grains__['os'] in dists:
            if int(__grains__['osrelease'].split('.')[0]) <= 5:
                return 'pkg'
            else:
                return False
        else:
            return False


def _parse_yum(arg):
    '''
    A small helper to parse yum output; returns a list of namedtuples
    '''
    cmd = 'yum -q {0}'.format(arg)
    out = __salt__['cmd.run_stdout'](cmd)
    YumOut = namedtuple('YumOut', ('name', 'version', 'status'))

    results = []

    for line in out.split('\n'):
        if len(line.split()) == 3:
            namearchstr, pkgver, pkgstatus = line.split()
            pkgname = namearchstr.rpartition('.')[0]

            results.append(YumOut(pkgname, pkgver, pkgstatus))

    return results


def _list_removed(old, new):
    '''
    List the packages which have been removed between the two package objects
    '''
    pkgs = []
    for pkg in old:
        if pkg not in new:
            pkgs.append(pkg)
    return pkgs


def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    out = _parse_yum('list updates {0}'.format(name))
    return out[0].version if out else ''


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return available_version(name) != ''


def version(name):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example::

        salt '*' pkg.version <package name>
    '''
    pkgs = list_pkgs()
    if name in pkgs:
        return pkgs[name]
    else:
        return ''


def list_pkgs():
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    out = _parse_yum('list installed')
    return dict([(i.name, i.version) for i in out])


def list_upgrades():
    '''
    Check whether or not an upgrade is available for all packages

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
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
    retcode = __salt__['cmd.retcode'](cmd)
    return True


def install(pkg, refresh=False, repo='', skip_verify=False, **kwargs):
    '''
    Install the passed package

    pkg
        The name of the package to be installed
    refresh : False
        Clean out the yum database before executing
    repo : (default)
        Specify a package repository to install from
        (e.g., ``yum --enablerepo=somerepo``)
    skip_verify : False
        Skip the GPG verification check (e.g., ``--nogpgcheck``)

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.install <package name>
    '''
    old = list_pkgs()

    cmd = 'yum -y {repo} {gpgcheck} install {pkg}'.format(
        repo='--enablerepo={0}'.format(repo) if repo else '',
        gpgcheck='--nogpgcheck' if skip_verify else '',
        pkg=pkg,
    )

    if refresh:
        refresh_db()
    retcode = __salt__['cmd.retcode'](cmd)
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


def upgrade():
    '''
    Run a full system upgrade, a yum upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.upgrade
    '''
    old = list_pkgs()
    cmd = 'yum -q -y upgrade'
    retcode = __salt__['cmd.retcode'](cmd)
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


def remove(pkg):
    '''
    Remove a single package with yum remove

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    old = list_pkgs()
    cmd = 'yum -q -y remove ' + pkg
    retcode = __salt__['cmd.retcode'](cmd)
    new = list_pkgs()
    return _list_removed(old, new)


def purge(pkg):
    '''
    Yum does not have a purge, this function calls remove

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    return remove(pkg)

