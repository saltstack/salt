'''
Package support for OpenBSD
'''

# Import python libs
import copy
import re
import logging

log = logging.getLogger(__name__)


__PKG_RE = re.compile('^((?:[^-]+|-(?![0-9]))+)-([0-9][^-]*)(?:-(.*))?$')


# XXX need a way of setting PKG_PATH instead of inheriting from the environment

def __virtual__():
    '''
    Set the virtual pkg module if the os is OpenBSD
    '''
    if __grains__['os'] == 'OpenBSD':
        return 'pkg'
    return False


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    # 'removed' not yet implemented or not applicable
    if salt.utils.is_true(kwargs.get('removed')):
        return {}

    if 'pkg.list_pkgs' in __context__:
        if versions_as_list:
            return __context__['pkg.list_pkgs']
        else:
            ret = copy.deepcopy(__context__['pkg.list_pkgs'])
            __salt__['pkg_resource.stringify'](ret)
            return ret

    ret = {}
    cmd = 'pkg_info -q -a'
    out = __salt__['cmd.run_all'](cmd).get('stdout', '')
    for line in out.splitlines():
        try:
            pkgname, pkgver, flavor = __PKG_RE.match(line).groups()
        except AttributeError:
            continue
        pkgname += '--{0}'.format(flavor) if flavor else ''
        __salt__['pkg_resource.add_pkg'](ret, pkgname, pkgver)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def latest_version(*names, **kwargs):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.latest_version <package name>
    '''
    pkgs = list_pkgs()
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ''

    stems = [x.split('--')[0] for x in names]
    cmd = 'pkg_info -q -I {0}'.format(' '.join(stems))
    for line in __salt__['cmd.run_all'](cmd).get('stdout', '').splitlines():
        try:
            pkgname, pkgver, flavor = __PKG_RE.match(line).groups()
        except AttributeError:
            continue
        pkgname += '--{0}'.format(flavor) if flavor else ''
        cur = pkgs.get(pkgname, '')
        if not cur or __salt__['pkg_resource.compare'](pkg1=cur,
                                                       oper='<',
                                                       pkg2=pkgver):
            ret[pkgname] = pkgver

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

    CLI Example, Install more than one package from a alternate source (e.g. salt file-server, HTTP, FTP, local filesystem)::

        salt '*' pkg.install sources='[{"<pkg name>": "salt://pkgs/<pkg filename>"}]'
    '''
    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources,
                                                                  **kwargs)
    if pkg_params is None or len(pkg_params) == 0:
        return {}

    old = list_pkgs()
    for pkg in pkg_params:
        if pkg_type == 'repository':
            stem, flavor = (pkg.split('--') + [''])[:2]
            pkg = '--'.join((stem, flavor))
        cmd = 'pkg_add -x {0}'.format(pkg)
        __salt__['cmd.run_all'](cmd)

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def remove(name=None, pkgs=None, **kwargs):
    '''
    Remove a single package with pkg_delete

    Returns a list containing the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    old = list_pkgs()
    pkg_params = [x.split('--')[0] for x in
                  __salt__['pkg_resource.parse_targets'](name, pkgs)[0]]
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}

    cmd = 'pkg_delete -xD dependencies {0}'.format(' '.join(targets))
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def purge(name=None, pkgs=None, **kwargs):
    '''
    Package purges are not supported, this function is identical to
    ``remove()``.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.


    Returns a dict containing the changes.

    CLI Example::

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    return remove(name=name, pkgs=pkgs)


def perform_cmp(pkg1='', pkg2=''):
    '''
    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    CLI Example::

        salt '*' pkg.perform_cmp '0.2.4' '0.2.4.1'
        salt '*' pkg.perform_cmp pkg1='0.2.4' pkg2='0.2.4.1'
    '''
    return __salt__['pkg_resource.perform_cmp'](pkg1=pkg1, pkg2=pkg2)


def compare(pkg1='', oper='==', pkg2=''):
    '''
    Compare two version strings.

    CLI Example::

        salt '*' pkg.compare '0.2.4' '<' '0.2.4.1'
        salt '*' pkg.compare pkg1='0.2.4' oper='<' pkg2='0.2.4.1'
    '''
    return __salt__['pkg_resource.compare'](pkg1=pkg1, oper=oper, pkg2=pkg2)
