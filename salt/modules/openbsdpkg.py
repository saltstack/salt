'''
Package support for OpenBSD
'''

import re


# XXX need a way of setting PKG_PATH instead of inheriting from the environment


def __virtual__():
    '''
    Set the virtual pkg module if the os is OpenBSD
    '''
    if __grains__['os'] == 'OpenBSD':
        return 'pkg'
    return False


def _splitpkg(name):
    if name:
        m = re.match('^((?:[^-]+|-(?![0-9]))+)-([0-9][^-]*)(?:-(.*))?$', name)
        if m:
            return m.groups()


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


def _get_pkgs():
    pkg = {}
    cmd = 'pkg_info -q -a'
    for line in __salt__['cmd.run'](cmd).split('\n'):
        namever = _splitpkg(line)
        if namever:
            pkg[namever[0]] = namever
    return pkg


def _format_pkgs(split):
    pkg = {}
    for k, v in split.items():
        if v[2]:
            name = '%s--%s' % (v[0], v[2])
        else:
            name = v[0]
        pkg[name] = v[1]
    return pkg


def list_pkgs():
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    return _format_pkgs(_get_pkgs())


def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    cmd = 'pkg_info -q -I {0}'.format(name)
    namever = _splitpkg(__salt__['cmd.run'](cmd))
    if namever:
        return namever[1]
    return ''


def version(name):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example::

        salt '*' pkg.version <package name>
    '''
    cmd = 'unset PKG_PATH; pkg_info -q -I {0}'.format(name)
    namever = _splitpkg(__salt__['cmd.run'](cmd))
    if namever:
        return namever[1]
    return ''


def install(name, *args, **kwargs):
    '''
    Install the passed package

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.install <package name>
    '''
    old = _get_pkgs()
    stem, flavor = (name.split('--') + [''])[:2]
    name = '--'.join((stem, flavor))
    # XXX it would be nice to be able to replace one flavor with another here
    if stem in old:
        cmd = 'pkg_add -u {0}'.format(name)
    else:
        cmd = 'pkg_add {0}'.format(name)
    __salt__['cmd.retcode'](cmd)
    new = _format_pkgs(_get_pkgs())
    return _compare_versions(_format_pkgs(old), new)


def remove(name):
    '''
    Remove a single package with pkg_delete

    Returns a list containing the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    old = _get_pkgs()
    stem, flavor = (name.split('--') + [''])[:2]
    if stem in old:
        cmd = 'pkg_delete -D dependencies {0}'.format(stem)
        __salt__['cmd.retcode'](cmd)
    new = _format_pkgs(_get_pkgs())
    return _list_removed(_format_pkgs(old), new)


def purge(name):
    '''
    Remove a single package with pkg_delete

    Returns a list containing the removed packages.

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    return remove(name)
