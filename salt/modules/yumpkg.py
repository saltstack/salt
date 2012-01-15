'''
Support for YUM
'''
import yum
import rpm
import logging
from rpmUtils.arch import getBaseArch

log = logging.getLogger(__name__)

def __virtual__():
    '''
    Confine this module to yum based systems
    '''
    # Return this for pkg on RHEL/Fedora based distros that ship with python
    # 2.6 or greater.
    dists = ('CentOS', 'Scientific', 'RedHat')
    if __grains__['os'] == 'Fedora':
        if int(__grains__['osrelease'].split('.')[0]) >= 11:
            return 'pkg'
        else:
            return False
    else:
        if __grains__['os'] in dists:
            if int(__grains__['osrelease'].split('.')[0]) >= 6:
                return 'pkg'
        else:
            return False


def _list_removed(old, new):
    '''
    List the packages which have been removed between the two package objects
    '''
    pkgs = []
    for pkg in old:
        if pkg not in new:
            pkgs.append(pkg)

    return pkgs


def _compare_versions(old, new):
    '''
    Returns a dict that that displays old and new versions for a package after
    install/upgrade of package.
    '''
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


def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    yb = yum.YumBase()
    # look for available packages only, if package is already installed with
    # latest version it will not show up here.  If we want to use wildcards
    # here we can, but for now its exact match only.
    versions_list = []
    for pkgtype in ['available', 'updates']:

        pl = yb.doPackageLists(pkgtype)
        exactmatch, matched, unmatched = yum.packages.parsePackages(pl, [name])
        # build a list of available packages from either available or updates
        # this will result in a double match for a package that is already
        # installed.  Maybe we should just return the value if we get a hit
        # on available, and only iterate though updates if we don't..
        for pkg in exactmatch:
            if pkg.arch == getBaseArch():
                rel = pkg.release.rpartition('.')[0]
                versions_list.append('-'.join([pkg.version, rel]))

    if len(versions_list) == 0:
        # if versions_list is empty return empty string.  It may make sense
        # to also check if a package is installed and on latest version
        # already and return a message saying 'up to date' or something along
        # those lines.
        return ''

    # remove the duplicate items from the list and return the first one
    return list(set(versions_list))[0]


def version(name):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example::

        salt '*' pkg.version <package name>
    '''
    pkgs = list_pkgs(name)
    if name in pkgs:
        return pkgs[name]
    else:
        return ''


def list_pkgs(*args):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    ts = rpm.TransactionSet()
    pkgs = {}
    # if no args are passed in get all packages
    if len(args) == 0:
        for h in ts.dbMatch():
            rel = h['release'].rpartition('.')[0]
            pkgs[h['name']] = '-'.join([h['version'], rel])
    else:
        # get package version for each package in *args
        for arg in args:
            for h in ts.dbMatch('name', arg):
                rel = h['release'].rpartition('.')[0]
                pkgs[h['name']] = '-'.join([h['version'], rel])

    return pkgs


def refresh_db():
    '''
    Since yum refreshes the database automatically, this runs a yum clean,
    so that the next yum operation will have a clean database

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    yb = yum.YumBase()
    yb.cleanMetadata()
    return True


def clean_metadata():
    '''
    Cleans local yum metadata.

    CLI Example::

        salt '*' pkg.clean_metadata
    '''
    return refresh_db()


def install(pkgs, refresh=False, repo='', skip_verify=False):
    '''
    Install the passed package(s)

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

        salt '*' pkg.install 'package package package'
    '''
    if refresh:
        refresh_db()

    if ',' in pkgs:
        pkgs = pkgs.split(',')
    else:
        pkgs = pkgs.split(' ')

    old = list_pkgs(*pkgs)

    yb = yum.YumBase()
    setattr(yb.conf, 'assumeyes', True)
    setattr(yb.conf, 'gpgcheck', not skip_verify)

    if repo:
        yb.repos.enableRepo(repo)

    for pkg in pkgs:
        try:
            yb.install(name=pkg)
        except yum.Errors.InstallError:
            log.error('Package {0} failed to install'.format(pkg))
    # Resolve Deps before attempting install.  This needs to be improved
    # by also tracking any deps that may get upgraded/installed during this
    # process.  For now only the version of the package(s) you request be
    # installed is tracked.
    yb.resolveDeps()
    yb.processTransaction(rpmDisplay=yum.rpmtrans.NoOutputCallBack())
    yb.closeRpmDB()

    new = list_pkgs(*pkgs)

    return _compare_versions(old, new)


def upgrade():
    '''
    Run a full system upgrade, a yum upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.upgrade
    '''

    yb = yum.YumBase()
    setattr(yb.conf, 'assumeyes', True)

    old = list_pkgs()

    # ideally we would look in the yum transaction and get info on all the
    # packages that are going to be upgraded and only look up old/new version
    # info on those packages.
    yb.update()
    yb.resolveDeps()
    yb.processTransaction(rpmDisplay=yum.rpmtrans.NoOutputCallBack())
    yb.closeRpmDB()

    new = list_pkgs()
    return _compare_versions(old, new)


def remove(pkgs):
    '''
    Removes packages with yum remove

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.remove <package,package,package>
    '''

    yb = yum.YumBase()
    setattr(yb.conf, 'assumeyes', True)
    pkgs = pkgs.split(',')
    old = list_pkgs(*pkgs)

    # same comments as in upgrade for remove.
    for pkg in pkgs:
        yb.remove(name=pkg)

    yb.resolveDeps()
    yb.processTransaction(rpmDisplay=yum.rpmtrans.NoOutputCallBack())
    yb.closeRpmDB()

    new = list_pkgs(*pkgs)

    return _list_removed(old, new)


def purge(pkgs):
    '''
    Yum does not have a purge, this function calls remove

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    return remove(pkgs)
