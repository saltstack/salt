'''
Support for YUM
'''

import logging
import os
import re
from collections import namedtuple


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
    YumOut = namedtuple('YumOut', ('name', 'version', 'status'))

    results = []

    for line in out.splitlines():
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


def _parse_pkg_meta(path):
    '''
    Retrieve package name and version number from package metadata
    '''
    name = ''
    version = ''
    rel = ''
    result = __salt__['cmd.run_all']('rpm -qpi "{0}"'.format(path))
    if result['retcode'] == 0:
        for line in result['stdout'].split('\n'):
            # Older versions of rpm command produce two-column output when run
            # with -qpi. So, regexes should not look for EOL after capture
            # group.
            if not name:
                m = re.match('^Name\s*:\s*(\S+)',line)
                if m:
                    name = m.group(1)
                    continue
            if not version:
                m = re.match('^Version\s*:\s*(\S+)',line)
                if m:
                    version = m.group(1)
                    continue
            if not rel:
                m = re.match('^Release\s*:\s*(\S+)',line)
                if m:
                    version = m.group(1)
                    continue
    if rel: version += '-{0}'.format(rel)
    return name,version


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
    __salt__['cmd.retcode'](cmd)
    return True


def install(name, refresh=False, repo='', skip_verify=False, source=None,
            **kwargs):
    '''
    Install the passed package

    name
        The name of the package to be installed

    refresh
        Clean out the yum database before executing

    repo
        Specify a package repository from which to install the package
        (e.g., ``yum --enablerepo=somerepo``)

    skip_verify
        Skip the GPG verification check (e.g., ``--nogpgcheck``)

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.install <package name>
    '''

    if source is not None:
        if __salt__['config.valid_fileproto'](source):
            # Cached RPM from master
            pkg_file = __salt__['cp.cache_file'](source)
            pkg_type = 'remote'
        else:
            # RPM file local to the minion
            pkg_file = source
            pkg_type = 'local'
        pname,pversion = _parse_pkg_meta(pkg_file)
        if not pname:
            pkg_file = None
            if pkg_type == 'remote':
                log.error('Failed to cache {0}. Are you sure this path is '
                          'correct?'.format(source))
            elif pkg_type == 'local':
                if not os.path.isfile(source):
                    log.error('Package file {0} not found. Are you sure this '
                              'path is correct?'.format(source))
                else:
                    log.error('Unable to parse package metadata for '
                              '{0}'.format(source))
        elif name != pname:
            pkg_file = None
            log.error('Package file {0} (Name: {1}) does not match the '
                      'specified package name ({2})'.format(source,
                                                            pname,
                                                            name))
        # Don't proceed if there was a problem with the package file
        if pkg_file is None: return {}

    cmd = 'yum -y {repo} {gpgcheck} install {pkg}'.format(
        repo='--enablerepo={0}'.format(repo) if repo else '',
        gpgcheck='--nogpgcheck' if skip_verify else '',
        pkg=pkg_file if source is not None else name,
    )

    if refresh: refresh_db()
    old = list_pkgs()
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
    old = list_pkgs()
    cmd = 'yum -q -y remove ' + pkg
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

