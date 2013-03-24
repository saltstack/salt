'''
Package support for OpenBSD
'''

# Import python libs
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
        try:
            return re.match(
                '^((?:[^-]+|-(?![0-9]))+)-([0-9][^-]*)(?:-(.*))?$',
                name
            ).groups()
        except AttributeError:
            pass


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


def _format_pkgs(split, versions_as_list=False):
    ret = {}
    for value in split.values():
        if value[2]:
            name = '{0}--{1}'.format(value[0], value[2])
        else:
            name = value[0]
        __salt__['pkg_resource.add_pkg'](ret, name, value[1])

    __salt__['pkg_resource.sort_pkglist'](ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def list_pkgs(versions_as_list=False):
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    return _format_pkgs(_get_pkgs(), versions_as_list=versions_as_list)


def latest_version(*names, **kwargs):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.latest_version <package name>
    '''
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        cmd = 'pkg_info -q -I {0}'.format(name)
        try:
            version = _splitpkg(__salt__['cmd.run'](cmd))[1]
            ret[name] = version
        except TypeError:
            ret[name] = ''

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = latest_version


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example::

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def install(name=None, pkgs=None, sources=None, **kwargs):
    '''
    Install the passed package

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

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
    new = list_pkgs()

    # New way
    return __salt__['pkg_resource.find_changes'](_format_pkgs(old), new)


def remove(name, **kwargs):
    '''
    Remove a single package with pkg_delete

    Returns a list containing the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    old = _get_pkgs()
    stem, _ = (name.split('--') + [''])[:2]
    if stem in old:
        cmd = 'pkg_delete -xD dependencies {0}'.format(stem)
        __salt__['cmd.retcode'](cmd)
    new = list_pkgs()
    return _list_removed(_format_pkgs(old), new)


def purge(name, **kwargs):
    '''
    Remove a single package with pkg_delete

    Returns a list containing the removed packages.

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    return remove(name)


def compare(version1='', version2=''):
    '''
    Compare two version strings. Return -1 if version1 < version2,
    0 if version1 == version2, and 1 if version1 > version2. Return None if
    there was a problem making the comparison.

    CLI Example::

        salt '*' pkg.compare '0.2.4-0' '0.2.4.1-0'
    '''
    return __salt__['pkg_resource.compare'](version1, version2)
