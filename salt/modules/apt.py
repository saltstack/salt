'''
Support for APT (Advanced Packaging Tool)
'''


def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''

    return 'pkg' if __grains__['os'] == 'Debian' else False


def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    version = ''
    cmd = 'apt-cache show {0} | grep Version'.format(name)

    out = __salt__['cmd.run_stdout'](cmd)

    version_list = out.split()
    if len(version_list) >= 2:
        version = version_list[1]

    return version


def version(name):
    '''
    Returns a string representing the package version or an empty string if not
    installed

    CLI Example::

        salt '*' pkg.version <package name>
    '''
    pkgs = list_pkgs(name)
    if name in pkgs:
        return pkgs[name]
    else:
        return ''


def refresh_db():
    '''
    Updates the APT database to latest packages based upon repositories

    Returns a dict::

        {'<database name>': Bool}

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    cmd = 'apt-get update'

    out = __salt__['cmd.run_stdout'](cmd)

    servers = {}
    for line in out:
        cols = line.split()
        if not len(cols):
            continue
        ident = " ".join(cols[1:4])
        if cols[0].count('Get'):
            servers[ident] = True
        else:
            servers[ident] = False

    return servers


def install(pkg, refresh=False):
    '''
    Install the passed package

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.install <package name>
    '''
    if refresh:
        refresh_db()

    ret_pkgs = {}
    old_pkgs = list_pkgs()
    cmd = 'apt-get -y install {0}'.format(pkg)
    __salt__['cmd.retcode'](cmd)
    new_pkgs = list_pkgs()

    for pkg in new_pkgs:
        if pkg in old_pkgs:
            if old_pkgs[pkg] == new_pkgs[pkg]:
                continue
            else:
                ret_pkgs[pkg] = {'old': old_pkgs[pkg],
                             'new': new_pkgs[pkg]}
        else:
            ret_pkgs[pkg] = {'old': '',
                         'new': new_pkgs[pkg]}

    return ret_pkgs


def remove(pkg):
    '''
    Remove a single package via ``aptitude remove``

    Returns a list containing the names of the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    ret_pkgs = []
    old_pkgs = list_pkgs()

    cmd = 'apt-get -y remove {0}'.format(pkg)
    __salt__['cmd.retcode'](cmd)
    new_pkgs = list_pkgs()
    for pkg in old_pkgs:
        if pkg not in new_pkgs:
            ret_pkgs.append(pkg)

    return ret_pkgs


def purge(pkg):
    '''
    Remove a package via aptitude along with all configuration files and
    unused dependencies.

    Returns a list containing the names of the removed packages

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    ret_pkgs = []
    old_pkgs = list_pkgs()

    # Remove inital package
    purge_cmd = 'apt-get -y purge {0}'.format(pkg)
    __salt__['cmd.retcode'](purge_cmd)
    
    new_pkgs = list_pkgs()
    
    for pkg in old_pkgs:
        if pkg not in new_pkgs:
            ret_pkgs.append(pkg)

    return ret_pkgs


def upgrade(refresh=True):
    '''
    Upgrades all packages via aptitude full-upgrade

    Returns a list of dicts containing the package names, and the new and old
    versions::

        [
            {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>']
            }',
            ...
        ]

    CLI Example::

        salt '*' pkg.upgrade
    '''

    if refresh:
        refresh_db()

    ret_pkgs = {}
    old_pkgs = list_pkgs()
    cmd = 'apt-get -y dist-upgrade'
    __salt__['cmd.retcode'](cmd)
    new_pkgs = list_pkgs()

    for pkg in new_pkgs:
        if pkg in old_pkgs:
            if old_pkgs[pkg] == new_pkgs[pkg]:
                continue
            else:
                ret_pkgs[pkg] = {'old': old_pkgs[pkg],
                             'new': new_pkgs[pkg]}
        else:
            ret_pkgs[pkg] = {'old': '',
                         'new': new_pkgs[pkg]}

    return ret_pkgs


def list_pkgs(regex_string=""):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    ret = {}
    cmd = 'dpkg --list {0}'.format(regex_string)

    out = __salt__['cmd.run_stdout'](cmd)

    for line in out.split('\n'):
        cols = line.split()
        if len(cols) and cols[0].count('ii'):
            ret[cols[1]] = cols[2]

    return ret
