'''
Pkgutil support for Solaris
'''

# Import python libs
import copy

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Set the virtual pkg module if the os is Solaris
    '''
    if __grains__['os'] == 'Solaris':
        return 'pkgutil'
    return False


def refresh_db():
    '''
    Updates the pkgutil repo database (pkgutil -U)

    CLI Example::

        salt '*' pkgutil.refresh_db
    '''
    return __salt__['cmd.retcode']('/opt/csw/bin/pkgutil -U > /dev/null 2>&1') == 0


def upgrade_available(name):
    '''
    Check if there is an upgrade available for a certain package

    CLI Example::

        salt '*' pkgutil.upgrade_available CSWpython
    '''
    version_num = None
    cmd = '/opt/csw/bin/pkgutil -c --parse --single {0} 2>/dev/null'.format(
        name)
    out = __salt__['cmd.run_stdout'](cmd)
    if out:
        version_num = out.split()[2].strip()
    if version_num:
        if version_num == "SAME":
            return ''
        else:
            return version_num
    return ''


def list_upgrades(refresh=True):
    '''
    List all available package upgrades on this system

    CLI Example::

        salt '*' pkgutil.list_upgrades
    '''
    if salt.utils.is_true(refresh):
        refresh_db()
    upgrades = {}
    lines = __salt__['cmd.run_stdout'](
        '/opt/csw/bin/pkgutil -A --parse').splitlines()
    for line in lines:
        comps = line.split('\t')
        if comps[2] == "SAME":
            continue
        if comps[2] == "not installed":
            continue
        upgrades[comps[0]] = comps[1]
    return upgrades


def upgrade(refresh=True, **kwargs):
    '''
    Upgrade all of the packages to the latest available version.

    Returns a dict containing the changes::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkgutil.upgrade
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    old = list_pkgs()

    # Install or upgrade the package
    # If package is already installed
    cmd = '/opt/csw/bin/pkgutil -yu'
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs versions_as_list=True
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
    cmd = '/usr/bin/pkginfo -x'

    # Package information returned two lines per package. On even-offset
    # lines, the package name is in the first column. On odd-offset lines, the
    # package version is in the second column.
    lines = __salt__['cmd.run'](cmd).splitlines()
    for index in range(0, len(lines)):
        if index % 2 == 0:
            name = lines[index].split()[0].strip()
        if index % 2 == 1:
            version_num = lines[index].split()[1].strip()
            __salt__['pkg_resource.add_pkg'](ret, name, version_num)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def version(*names, **kwargs):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example::

        salt '*' pkgutil.version CSWpython
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def latest_version(name, **kwargs):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkgutil.latest_version CSWpython
    '''
    cmd = '/opt/csw/bin/pkgutil -a --parse {0}'.format(name)
    namever = __salt__['cmd.run_stdout'](cmd).split()[2].strip()
    if namever:
        return namever
    return ''

# available_version is being deprecated
available_version = latest_version


def install(name=None, refresh=False, version=None, pkgs=None, **kwargs):
    '''
    Install packages using the pkgutil tool.

    CLI Example::

        salt '*' pkg.install <package_name>
        salt '*' pkg.install SMClgcc346


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from OpenCSW. Must be passed as a python
        list.

        CLI Example::
            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3"}]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    '''
    if refresh:
        refresh_db()

    # Ignore 'sources' argument
    pkg_params = __salt__['pkg_resource.parse_targets'](name,
                                                        pkgs,
                                                        **kwargs)[0]

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    if pkgs is None and version and len(pkg_params) == 1:
        pkg_params = {name: version}
    targets = []
    for param, pkgver in pkg_params.iteritems():
        if pkgver is None:
            targets.append(param)
        else:
            targets.append('{0}-{1}'.format(param, pkgver))

    cmd = '/opt/csw/bin/pkgutil -yu {0}'.format(' '.join(targets))
    old = list_pkgs()
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def remove(name=None, pkgs=None, **kwargs):
    '''
    Remove a package and all its dependencies which are not in use by other
    packages.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.


    Returns a dict containing the changes.

    CLI Example::

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    cmd = '/opt/csw/bin/pkgutil -yr {0}'.format(' '.join(targets))
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

        salt '*' pkg.perform_cmp '0.2.4-0' '0.2.4.1-0'
        salt '*' pkg.perform_cmp pkg1='0.2.4-0' pkg2='0.2.4.1-0'
    '''
    return __salt__['pkg_resource.perform_cmp'](pkg1=pkg1, pkg2=pkg2)


def compare(pkg1='', oper='==', pkg2=''):
    '''
    Compare two version strings.

    CLI Example::

        salt '*' pkg.compare '0.2.4-0' '<' '0.2.4.1-0'
        salt '*' pkg.compare pkg1='0.2.4-0' oper='<' pkg2='0.2.4.1-0'
    '''
    return __salt__['pkg_resource.compare'](pkg1=pkg1, oper=oper, pkg2=pkg2)
