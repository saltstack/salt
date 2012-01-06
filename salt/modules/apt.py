'''
Support for APT (Advanced Packaging Tool)
'''


def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''

    return 'pkg' if __grains__['os'] in [ 'Debian', 'Ubuntu' ] else False


def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    version = ''
    cmd = 'apt-cache -q show {0} | grep Version'.format(name)

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
    cmd = 'apt-get -q update'

    out = __salt__['cmd.run_stdout'](cmd)

    servers = {}
    for line in out:
        cols = line.split()
        if not len(cols):
            continue
        ident = " ".join(cols[1:4])
        if 'Get' in cols[0]:
            servers[ident] = True
        else:
            servers[ident] = False

    return servers


def install(pkg, refresh=False, repo='', skip_verify=False):
    '''
    Install the passed package

    pkg
        The name of the package to be installed
    refresh : False
        Update apt before continuing
    repo : (default)
        Specify a package repository to install from
        (e.g., ``apt-get -t unstable install somepackage``)
    skip_verify : False
        Skip the GPG verification check (e.g., ``--allow-unauthenticated``)

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

    cmd = '{nonint} apt-get -q -y {confold}{verify}{target} install {pkg}'.format(
            nonint='DEBIAN_FRONTEND=noninteractive',
            confold='-o DPkg::Options::=--force-confold',
            verify='--allow-unauthenticated' if skip_verify else '',
            target=' -t {0}'.format(repo) if repo else '',
            pkg=pkg)

    __salt__['cmd.run'](cmd)
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
    Remove a single package via ``apt-get remove``

    Returns a list containing the names of the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    ret_pkgs = []
    old_pkgs = list_pkgs()

    cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -q -y remove {0}'.format(pkg)
    __salt__['cmd.run'](cmd)
    new_pkgs = list_pkgs()
    for pkg in old_pkgs:
        if pkg not in new_pkgs:
            ret_pkgs.append(pkg)

    return ret_pkgs


def purge(pkg):
    '''
    Remove a package via ``apt-get purge`` along with all configuration
    files and unused dependencies.

    Returns a list containing the names of the removed packages

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    ret_pkgs = []
    old_pkgs = list_pkgs()

    # Remove inital package
    purge_cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -q -y purge {0}'.format(pkg)
    __salt__['cmd.run'](purge_cmd)

    new_pkgs = list_pkgs()

    for pkg in old_pkgs:
        if pkg not in new_pkgs:
            ret_pkgs.append(pkg)

    return ret_pkgs


def upgrade(refresh=True):
    '''
    Upgrades all packages via ``apt-get dist-upgrade``

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
    cmd = 'DEBIAN_FRONTEND=noninteractive apt-get -q -y -o DPkg::Options::=--force-confold dist-upgrade'
    __salt__['cmd.run'](cmd)
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
        if len(cols) and 'ii' in cols[0]:
            ret[cols[1]] = cols[2]

    return ret
