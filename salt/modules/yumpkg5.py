'''
Support for YUM
'''
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
    out = __salt__['cmd.run_stdout']('yum list {0} -q'.format(name))
    for line in out.split('\n'):
        if not line.strip():
            continue
        # Iterate through the output
        comps = line.split()
        if comps[0].split('.')[0] == name:
            if len(comps) < 2:
                continue
            # found it!
            return comps[1][:comps[1].rindex('.')]
    # Package not available
    return ''


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
    cmd = "rpm -qa --qf '%{NAME}:%{VERSION}-%{RELEASE};'"
    ret = {}
    out = __salt__['cmd.run_stdout'](cmd)
    for line in out.split(';'):
        if ':' not in line:
            continue
        comps = line.split(':')
        ret[comps[0]] = comps[1]
    return ret


def refresh_db():
    '''
    Since yum refreshes the database automatically, this runs a yum clean,
    so that the next yum operation will have a clean database

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    cmd = 'yum clean dbcache'
    retcode = __salt__['cmd.retcode'](cmd)
    return True


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
    old = list_pkgs()
    cmd = 'yum -y install ' + pkg
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
    cmd = 'yum -y upgrade'
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
    cmd = 'yum -y remove ' + pkg
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

