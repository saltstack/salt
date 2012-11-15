'''
A module to wrap pacman calls, since Arch is the best
(https://wiki.archlinux.org/index.php/Arch_is_the_best)
'''

import logging
import os
import re

log = logging.getLogger(__name__)

def __virtual__():
    '''
    Set the virtual pkg module if the os is Arch
    '''
    return 'pkg' if __grains__['os'] == 'Arch' else False


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
    result = __salt__['cmd.run_all']('pacman -Qpi "{0}"'.format(path))
    if result['retcode'] == 0:
        for line in result['stdout'].splitlines():
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
    return name,version


def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    return __salt__['cmd.run']('pacman -Sp --print-format %v {0}'.format(name))


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return name in __salt__['cmd.run'](
            'pacman -Spu --print-format %n | egrep "^\S+$"').split()


def list_upgrades():
    '''
    List all available package upgrades on this system

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    upgrades = {}
    lines = __salt__['cmd.run'](
            'pacman -Sypu --print-format "%n %v" | egrep -v "^\s|^:"'
            ).splitlines()
    for line in lines:
        comps = line.split(' ')
        if len(comps) < 2:
            continue
        upgrades[comps[0]] = comps[1]
    return upgrades


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
    cmd = 'pacman -Q'
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if not line:
            continue
        comps = line.split()
        ret[comps[0]] = comps[1]
    return ret


def refresh_db():
    '''
    Just run a ``pacman -Sy``, return a dict::

        {'<database name>': Bool}

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    cmd = 'LANG=C pacman -Sy'
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if line.strip().startswith('::'):
            continue
        if not line:
            continue
        key = line.strip().split()[0]
        if 'is up to date' in line:
            ret[key] = False
        elif 'downloading' in line:
            key = line.strip().split()[1].split('.')[0]
            ret[key] = True
    return ret


def install(name, refresh=False, source=None, **kwargs):
    '''
    Install the passed package, add refresh=True to install with an -Sy

    name
        Tha name of the package to be installed.

    refresh
        Whether or not to refresh the package database before installing.
        Defaults to False.

    source
        A package file to install.

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.install <package name>
    '''

    if source is not None:
        if __salt__['config.valid_fileproto'](source):
            # Cached package from master
            pkg_file = __salt__['cp.cache_file'](source)
            pkg_type = 'remote'
        else:
            # Package file local to the minion
            pkg_file = source
            pkg_type = 'local'
        pname,pversion = _parse_pkg_meta(pkg_file)
        if not pname:
            cmd = None
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
            log.error('Package file {0} (Name: {1}) does not match the '
                      'specified package name ({2})'.format(source,
                                                            pname,
                                                            name))
            cmd = None
        else:
            cmd = 'pacman -U --noprogressbar --noconfirm {0}'.format(pkg_file)
    else:
        fname = name
        for vkey, vsign in (('gt', '>'), ('lt', '<'),
                            ('eq', '='), ('version', '=')):
            if vkey in kwargs and kwargs[vkey] is not None:
                fname = '"{0}{1}{2}"'.format(name, vsign, kwargs[vkey])
                break
        if refresh:
            cmd = 'pacman -Syu --noprogressbar --noconfirm {0}'.format(fname)
        else:
            cmd = 'pacman -S --noprogressbar --noconfirm {0}'.format(fname)

    pkgs = {}
    if cmd is not None:
        old = list_pkgs()
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
    Run a full system upgrade, a pacman -Syu

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.upgrade
    '''
    old = list_pkgs()
    cmd = 'pacman -Syu --noprogressbar --noconfirm '
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
    Remove a single package with ``pacman -R``

    Return a list containing the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    old = list_pkgs()
    cmd = 'pacman -R --noprogressbar --noconfirm {0}'.format(name)
    __salt__['cmd.retcode'](cmd)
    new = list_pkgs()
    return _list_removed(old, new)


def purge(name):
    '''
    Recursively remove a package and all dependencies which were installed
    with it, this will call a ``pacman -Rsc``

    Return a list containing the removed packages.

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    old = list_pkgs()
    cmd = 'pacman -R --noprogressbar --noconfirm {0}'.format(name)
    __salt__['cmd.retcode'](cmd)
    new = list_pkgs()
    return _list_removed(old, new)
