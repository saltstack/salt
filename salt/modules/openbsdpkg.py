'''
Package support for OpenBSD
'''

# Import python libs
import os
import re
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


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


def _get_pkgs():
    pkg = {}
    cmd = 'pkg_info -q -a'
    for line in __salt__['cmd.run'](cmd).splitlines():
        namever = _splitpkg(line)
        if namever:
            pkg[namever[0]] = namever
    return pkg


def _format_pkgs(split):
    pkg = {}
    for k, v in split.items():
        if v[2]:
            name = '{0}--{1}'.format(v[0], v[2])
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


def install(name=None, pkgs=None, sources=None, **kwargs):
    '''
    Install the passed package

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example, Install one package::

        salt '*' pkg.install <package name>

    CLI Example, Install more than one package::

        salt '*' pkg.install pkgs='["<package name>", "<package name>"]'

    CLI Example, Install more than one package from a alternate source (e.g. salt file-server, http, ftp, local filesystem)::

        salt '*' pkg.install sources='[{"<pkg name>": "salt://pkgs/<pkg filename>"}]' 
    '''
    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources)
    if pkg_params is None or len(pkg_params) == 0:
        return {}

    # Get a list of the currently installed packages
    old = _get_pkgs()

    for pkg in pkg_params:
        if pkg_type == 'repository':
            stem, flavor = (pkg.split('--') + [''])[:2]
            pkg = '--'.join((stem, flavor))

            if stem in old:
                cmd = 'pkg_add -xu {0}'.format(pkg)
            else:
                cmd = 'pkg_add -x {0}'.format(pkg)
        else:
            cmd = 'pkg_add -x {0}'.format(pkg)

        stderr = __salt__['cmd.run_all'](cmd).get('stderr', '')
        if stderr:
            log.error(stderr)

    # Get a list of all the packages that are now installed.
    new = _format_pkgs(_get_pkgs())

    # New way
    return __salt__['pkg_resource.find_changes'](_format_pkgs(old), new)



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
        cmd = 'pkg_delete -xD dependencies {0}'.format(stem)
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
