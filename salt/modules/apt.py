'''
Support for APT (Advanced Packaging Tool)
'''

import os

def __virtual__():
    '''
    Confirm this module is on a Debian based system
    '''

    return 'pkg' if __grains__['os'] in ('Debian', 'Ubuntu') else False


def __init__():
    '''
    For Debian and derivative systems, set up
    a few env variables to keep apt happy and
    non-interactive.
    '''
    if __virtual__():
        env_vars = {
            'APT_LISTBUGS_FRONTEND': 'none',
            'APT_LISTCHANGES_FRONTEND': 'none',
            'DEBIAN_FRONTEND': 'noninteractive',
        }
        # Export these puppies so they persist
        os.environ.update(env_vars)


def available_version(name):
    '''
    Return the latest version of the named package available for upgrade or
    installation via the available apt repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    version = ''
    cmd = 'apt-cache -q show {0} | grep Version'.format(name)

    out = __salt__['cmd.run_stdout'](cmd)

    version_list = out.split()
    if len(version_list) >= 2:
        version = version_list[-1]

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


def install(pkg, refresh=False, repo='', skip_verify=False,
            debconf=None, version=None, **kwargs):
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
    debconf : None
        Provide the path to a debconf answers file, processed before
        installation.
    version : None
        Install a specific version of the package, e.g. 1.0.9~ubuntu

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.install <package name>
    '''
    salt.utils.daemonize_if(__opts__['multiprocessing'])
    if refresh:
        refresh_db()

    if debconf:
        __salt__['debconf.set_file'](debconf)

    ret_pkgs = {}
    old_pkgs = list_pkgs()

    if version:
        pkg = "{0}={1}".format(pkg, version)

    cmd = 'apt-get -q -y {confold}{verify}{target} install {pkg}'.format(
            confold=' -o DPkg::Options::=--force-confold',
            verify=' --allow-unauthenticated' if skip_verify else '',
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

    cmd = 'apt-get -q -y remove {0}'.format(pkg)
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
    purge_cmd = 'apt-get -q -y purge {0}'.format(pkg)
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
    salt.utils.daemonize_if(__opts__['multiprocessing'])
    if refresh:
        refresh_db()

    ret_pkgs = {}
    old_pkgs = list_pkgs()
    cmd = 'apt-get -q -y -o DPkg::Options::=--force-confold dist-upgrade'
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

    External dependencies::

        Virtual package resolution requires aptitude.
        Without aptitude virtual packages will be reported as not installed.

    CLI Example::

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs httpd
    '''
    ret = {}
    cmd = 'dpkg --list {0}'.format(regex_string)

    out = __salt__['cmd.run_stdout'](cmd)

    for line in out.split('\n'):
        cols = line.split()
        if len(cols) and 'ii' in cols[0]:
            ret[cols[1]] = cols[2]

    # If ret is empty at this point, check to see if the package is virtual.
    # We also need aptitude past this point.
    if not ret and __salt__['cmd.has_exec']('aptitude'):
        cmd = ('aptitude search "{0} ?virtual ?reverse-provides(?installed)"'
                .format(regex_string))

        out = __salt__['cmd.run_stdout'](cmd)
        if out:
            ret[regex_string] = '1' # Setting all 'installed' virtual package
                                    # versions to '1'

    return ret


def upgrade_available(name):

    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    cmd = 'apt-get --just-print upgrade'
    out = __salt__['cmd.run_stdout'](cmd)

    # Mini filter function
    def _to_update(line):
        return line.startswith("Conf ")

    upgraded_packages = filter(_to_update, out.split('\n'))

    # Example line:
    # 'Conf linux-image-2.6.35-32-generic (2.6.35-32.66 Ubuntu:10.10/maverick-updates [amd64])'
    for line in upgraded_packages:
        data = line.split()
        if name == data[1]:
            return True
    return False
