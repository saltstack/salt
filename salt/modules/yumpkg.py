'''
Support for YUM
'''


def __virtual__():
    '''
    Confine this module to yum based systems
    '''
    # We don't need to support pre-yum OSes because they don't support
    # python <= 2.6
    dists = 'CentOS Scientific RedHat Fedora'
    return 'pkg' if dists.count(__grains__['os']) else False


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
    import yum
    from rpmUtils.arch import getBaseArch
    
    yb = yum.YumBase() 
    # look for available packages only, if package is already installed with 
    # latest version it will not show up here.  If we want to use wildcards
    # here we can, but for now its exactmatch only.
    
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
                versions_list.append('-'.join([pkg.version, pkg.release]))
    
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
    import rpm
    ts = rpm.TransactionSet()
    pkgs = {}
    # if no args are passed in get all packages
    if len(args) == 0:
        for h in ts.dbMatch():
            pkgs[h['name']] = '-'.join([h['version'],h['release']])
    else:
        # get package version for each package in *args
        for arg in args:
            for h in ts.dbMatch('name', arg):
                pkgs[h['name']] = '-'.join([h['version'],h['release']])
    
    return pkgs


def refresh_db():
    '''
    Since yum refreshes the database automatically, this runs a yum clean,
    so that the next yum operation will have a clean database

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    import yum
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


def install(pkg, refresh=False):
    '''
    Install the passed package, add refresh=True to clean out the yum database
    before executing

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.install <package name>
    '''
    
    # WIP only commiting this so I can keep working on it at home later...
    import yum

    if refresh:
        refresh_db()

    yb = yum.YumBase()
    
    try:        
        yb.install(name=pkg)
        yb.resolveDeps()
    except yum.Errors.InstallError, e:
        return False

    
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
    cmd = 'yum -y upgrade'
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


def remove(pkg):
    '''
    Remove a single package with yum remove

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
#    import subprocess as sp
    old = list_pkgs()
#    sp.Popen(['yum', '-y', 'remove', pkg])
    cmd = 'yum -y remove ' + pkg
    __salt__['cmd.retcode'](cmd)
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
