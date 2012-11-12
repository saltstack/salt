'''
Package support for openSUSE via the zypper package manager
'''

import logging
import os
import re

log = logging.getLogger(__name__)

def __virtual__():
    '''
    Set the virtual pkg module if the os is openSUSE
    '''
    return 'pkg' if __grains__.get('os_family', '') == 'Suse' else False


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
        for line in result['stdout'].splitlines():
            if not name:
                m = re.match('^Name\s*:\s*(\S+)', line)
                if m:
                    name = m.group(1)
                    continue
            if not version:
                m = re.match('^Version\s*:\s*(\S+)', line)
                if m:
                    version = m.group(1)
                    continue
            if not rel:
                m = re.match('^Release\s*:\s*(\S+)', line)
                if m:
                    version = m.group(1)
                    continue
    if rel:
        version += '-{0}'.format(rel)
    return name, version


def _available_versions():
    '''
    The available versions of packages
    '''
    cmd = 'zypper packages -i'
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if not line:
            continue
        if '|' not in line:
            continue
        comps = []
        for comp in line.split('|'):
            comps.append(comp.strip())
        if comps[0] == 'v':
            ret[comps[2]] = comps[3]
    return ret

def available_version(name):
    '''
    Return the available version of a given package

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    avail = _available_versions()
    return avail.get(name, '')

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
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    cmd = 'rpm -qa --queryformat "%{NAME}_|-%{VERSION}_|-%{RELEASE}\n"'
    ret = {}
    for line in __salt__['cmd.run'](cmd).splitlines():
        name, version, rel = line.split('_|-')
        pkgver = version
        if rel: pkgver += '-{0}'.format(rel)
        ret[name] = pkgver
    return ret


def refresh_db():
    '''
    Just run a ``zypper refresh``, return a dict::

        {'<database name>': Bool}

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    cmd = 'zypper refresh'
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if not line:
            continue
        if line.strip().startswith('Repository'):
            key = line.split("'")[1].strip()
            if 'is up to date' in line:
                ret[key] = False
        elif line.strip().startswith('Building'):
            key = line.split("'")[1].strip()
            if 'done' in line:
                ret[key] = True
    return ret


def install(name, refresh=False, source=None, **kwargs):
    '''
    Install the passed package, add refresh=True to run 'zypper refresh' before
    package is installed.

    name
        The name of the package to be installed.

    refresh
        Whether or not to refresh the package database before installing.
        Defaults to False.

    source
        An RPM package to install.

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
            zypper_param = None
            if pkg_type == 'remote':
                log.error('Failed to cache {0}. Are you sure this path is '
                          'correct?'.format(source))
            elif pkg_type == 'local':
                if not os.path.isfile(source):
                    log.error('RPM resource {0} not found. Are you sure this '
                              'path is correct?'.format(source))
                else:
                    log.error('Unable to parse RPM metadata for '
                              '{0}.'.format(source))
        elif name == pname:
            zypper_param = pkg_file
        else:
            log.error('Package file {0} (Name: {1}) does not match the '
                      'specified package name ({2})'.format(source,
                                                            pname,
                                                            name))
            zypper_param = None
    else:
        zypper_param = name

    pkgs = {}
    if zypper_param is not None:
        old = list_pkgs()
        if refresh:
            refresh_db()
        cmd = 'zypper -n install -l {0}'.format(zypper_param)
        __salt__['cmd.retcode'](cmd)
        new = list_pkgs()
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
    Run a full system upgrade, a zypper upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.upgrade
    '''
    old = list_pkgs()
    cmd = 'zypper -n up -l'
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


def remove(name):
    '''
    Remove a single package with ``zypper remove``

    Return a list containing the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    old = list_pkgs()
    cmd = 'zypper -n remove {0}'.format(name)
    __salt__['cmd.retcode'](cmd)
    new = list_pkgs()
    return _list_removed(old, new)


def purge(name):
    '''
    Recursively remove a package and all dependencies which were installed
    with it, this will call a ``zypper remove -u``

    Return a list containing the removed packages.

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    old = list_pkgs()
    cmd = 'zypper -n remove -u {0}'.format(name)
    __salt__['cmd.retcode'](cmd)
    new = list_pkgs()
    return _list_removed(old, new)
