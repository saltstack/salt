# -*- coding: utf-8 -*-
'''
A module to manage software on Windows

:depends:   - win32com
            - win32con
            - win32api
            - pywintypes
'''

# Import third party libs
try:
    import win32api
    import win32con
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

# Import python libs
import logging
try:
    import msgpack
except ImportError:
    import msgpack_pure as msgpack
import os
import locale
from distutils.version import LooseVersion  # pylint: disable=E0611

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Set the virtual pkg module if the os is Windows
    '''
    if salt.utils.is_windows() and HAS_DEPENDENCIES:
        return __virtualname__
    return False


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...

    '''
    if len(names) == 0:
        return ''

    # Initialize the return dict with empty strings
    ret = {}
    for name in names:
        ret[name] = ''

    # Refresh before looking for the latest version available
    if salt.utils.is_true(kwargs.get('refresh', True)):
        refresh_db()

    installed_pkgs = list_pkgs(versions_as_list=True)
    log.trace('List of installed packages: {0}'.format(installed_pkgs))

    # iterate over all requested package names
    for name in names:
        latest_installed = '0'
        latest_available = '0'

        # get latest installed version of package
        if name in installed_pkgs:
            log.trace('Sorting out the latest available version of {0}'.format(name))
            latest_installed = sorted(installed_pkgs[name], cmp=_reverse_cmp_pkg_versions).pop()
            log.debug('Latest installed version of package {0} is {1}'.format(name, latest_installed))

        # get latest available (from win_repo) version of package
        pkg_info = _get_package_info(name)
        log.trace('Raw win_repo pkg_info for {0} is {1}'.format(name, pkg_info))
        latest_available = _get_latest_pkg_version(pkg_info)
        if latest_available:
            log.debug('Latest available version of package {0} is {1}'.format(name, latest_available))

            # check, whether latest available version is newer than latest installed version
            if salt.utils.compare_versions(ver1=str(latest_available),
                                           oper='>',
                                           ver2=str(latest_installed)):
                log.debug('Upgrade of {0} from {1} to {2} is available'.format(name, latest_installed, latest_available))
                ret[name] = latest_available
            else:
                log.debug('No newer version than {0} of {1} is available'.format(latest_installed, name))
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = latest_version


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    return latest_version(name) != ''


def list_upgrades(refresh=True):
    '''
    List all available package upgrades on this system

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    ret = {}
    for name, data in get_repo_data().get('repo', {}).items():
        if version(name):
            latest = latest_version(name)
            if latest:
                ret[name] = latest
    return ret


def list_available(*names):
    '''
    Return a list of available versions of the specified package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_available <package name>
        salt '*' pkg.list_available <package name01> <package name02>
    '''
    if not names:
        return ''
    if len(names) == 1:
        pkginfo = _get_package_info(names[0])
        if not pkginfo:
            return ''
        versions = pkginfo.keys()
    else:
        versions = {}
        for name in names:
            pkginfo = _get_package_info(name)
            if not pkginfo:
                continue
            versions[name] = pkginfo.keys() if pkginfo else []
    versions = sorted(versions, cmp=_reverse_cmp_pkg_versions)
    return versions


def version(*names, **kwargs):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
    '''
    win_names = []
    ret = {}
    if len(names) == 1:
        val = __salt__['pkg_resource.version'](*names, **kwargs)
        if len(val):
            return val
        return ''
    if len(names) > 1:
        reverse_dict = {}
        nums = __salt__['pkg_resource.version'](*names, **kwargs)
        if len(nums):
            for num, val in nums.iteritems():
                if len(val) > 0:
                    try:
                        ret[reverse_dict[num]] = val
                    except KeyError:
                        ret[num] = val
            return ret
        return dict([(x, '') for x in names])
    return ret


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs versions_as_list=True
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    # not yet implemented or not applicable
    if any([salt.utils.is_true(kwargs.get(x))
            for x in ('removed', 'purge_desired')]):
        return {}

    ret = {}
    name_map = _get_name_map()
    with salt.utils.winapi.Com():
        for key, val in _get_reg_software().iteritems():
            if key in name_map:
                key = name_map[key]
            __salt__['pkg_resource.add_pkg'](ret, key, val)

    __salt__['pkg_resource.sort_pkglist'](ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def _search_software(target):
    '''
    This searches the msi product databases for name matches
    of the list of target products, it will return a dict with
    values added to the list passed in
    '''
    search_results = {}
    software = dict(_get_reg_software().items())
    for key, value in software.items():
        if key is not None:
            if target.lower() in key.lower():
                search_results[key] = value
    return search_results


def _get_reg_software():
    '''
    This searches the uninstall keys in the registry to find
    a match in the sub keys, it will return a dict with the
    display name as the key and the version as the value
    '''
    reg_software = {}
    #This is a list of default OS reg entries that don't seem to be installed
    #software and no version information exists on any of these items
    ignore_list = ['AddressBook',
                   'Connection Manager',
                   'DirectDrawEx',
                   'Fontcore',
                   'IE40',
                   'IE4Data',
                   'IE5BAKEX',
                   'IEData',
                   'MobileOptionPack',
                   'SchedulingAgent',
                   'WIC'
                   ]
    encoding = locale.getpreferredencoding()

    #attempt to corral the wild west of the multiple ways to install
    #software in windows
    reg_entries = dict(_get_machine_keys().items())
    for reg_hive, reg_keys in reg_entries.items():
        for reg_key in reg_keys:
            try:
                reg_handle = win32api.RegOpenKeyEx(
                    reg_hive,
                    reg_key,
                    0,
                    win32con.KEY_READ)
            except Exception:
                pass
                #Unsinstall key may not exist for all users
            for name, num, blank, time in win32api.RegEnumKeyEx(reg_handle):
                prd_uninst_key = "\\".join([reg_key, name])
                #These reg values aren't guaranteed to exist
                windows_installer = _get_reg_value(
                    reg_hive,
                    prd_uninst_key,
                    'WindowsInstaller')

                prd_name = _get_reg_value(
                    reg_hive,
                    prd_uninst_key,
                    "DisplayName")
                try:
                    prd_name = prd_name.decode(encoding)
                except Exception:
                    pass
                prd_ver = _get_reg_value(
                    reg_hive,
                    prd_uninst_key,
                    "DisplayVersion")
                if name not in ignore_list:
                    if prd_name != 'Not Found':
                        # some MS Office updates don't register a product name which means
                        # their information is useless
                        if prd_name != '':
                            reg_software[prd_name] = prd_ver
    return reg_software


def _get_machine_keys():
    '''
    This will return the hive 'const' value and some registry keys where
    installed software information has been known to exist for the
    HKEY_LOCAL_MACHINE hive
    '''
    machine_hive_and_keys = {}
    machine_keys = [
        "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
        "Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
    ]
    machine_hive = win32con.HKEY_LOCAL_MACHINE
    machine_hive_and_keys[machine_hive] = machine_keys
    return machine_hive_and_keys


def _get_reg_value(reg_hive, reg_key, value_name=''):
    '''
    Read one value from Windows registry.
    If 'name' is empty map, reads default value.
    '''
    try:
        key_handle = win32api.RegOpenKeyEx(
            reg_hive, reg_key, 0, win32con.KEY_ALL_ACCESS)
        value_data, value_type = win32api.RegQueryValueEx(key_handle,
                                                          value_name)
        win32api.RegCloseKey(key_handle)
    except Exception:
        value_data = 'Not Found'
    return value_data


def refresh_db(saltenv='base'):
    '''
    Just recheck the repository and return a dict::

        {'<database name>': Bool}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    __context__.pop('winrepo.data', None)
    repocache = __opts__['win_repo_cachefile']
    cached_repo = __salt__['cp.is_cached'](repocache, saltenv)
    if not cached_repo:
        # It's not cached. Cache it, mate.
        cached_repo = __salt__['cp.cache_file'](repocache, saltenv)
        if not cached_repo:
            return False
        return True
    # Check if the master's cache file has changed
    if __salt__['cp.hash_file'](repocache) != __salt__['cp.hash_file'](cached_repo, saltenv):
        cached_repo = __salt__['cp.cache_file'](repocache, saltenv)
        if not cached_repo:
            return False
    return True


def install(name=None, refresh=False, pkgs=None, saltenv='base', **kwargs):
    '''
    Install the passed package

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.install <package name>
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    # Ignore pkg_type from parse_targets, Windows does not support the "sources"
    # argument
    pkg_params = __salt__['pkg_resource.parse_targets'](name,
                                                        pkgs,
                                                        **kwargs)[0]

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    old = list_pkgs()

    if pkgs is None and len(pkg_params) == 1:
        # Only use the 'version' param if 'name' was not specified as a
        # comma-separated list
        pkg_params = {name:
                         {
                             'version': kwargs.get('version'),
                             'extra_install_flags': kwargs.get('extra_install_flags')}}

    for pkg_name, options in pkg_params.iteritems():
        pkginfo = _get_package_info(pkg_name)
        if not pkginfo:
            log.error('Unable to locate package {0}'.format(pkg_name))
            continue

        version_num = options and options.get('version') or _get_latest_pkg_version(pkginfo)

        if version_num in [old.get(pkginfo[x]['full_name']) for x in pkginfo]:
            # Desired version number already installed
            continue
        elif version_num not in pkginfo:
            log.error('Version {0} not found for package '
                      '{1}'.format(version_num, pkg_name))
            continue

        installer = pkginfo[version_num].get('installer')
        if not installer:
            log.error('No installer configured for version {0} of package '
                      '{1}'.format(version_num, pkg_name))

        if installer.startswith('salt:') \
                or installer.startswith('http:') \
                or installer.startswith('https:') \
                or installer.startswith('ftp:'):
            cached_pkg = __salt__['cp.is_cached'](installer, saltenv)
            if not cached_pkg:
                # It's not cached. Cache it, mate.
                cached_pkg = __salt__['cp.cache_file'](installer, saltenv)
            if __salt__['cp.hash_file'](installer, saltenv) != \
                                          __salt__['cp.hash_file'](cached_pkg):
                cached_pkg = __salt__['cp.cache_file'](installer, saltenv)
        else:
            cached_pkg = installer

        cached_pkg = cached_pkg.replace('/', '\\')
        msiexec = pkginfo[version_num].get('msiexec')
        install_flags = '{0} {1}'.format(pkginfo[version_num]['install_flags'], options and options.get('extra_install_flags') or "")

        cmd = []
        if msiexec:
            cmd.extend(['msiexec', '/i'])
        cmd.append(cached_pkg)
        cmd.extend(install_flags.split())

        __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)

    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def upgrade(refresh=True):
    '''
    Run a full system upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''
    log.warning('pkg.upgrade not implemented on Windows yet')

    # Uncomment the below once pkg.upgrade has been implemented

    #if salt.utils.is_true(refresh):
    #    refresh_db()
    return {}


def remove(name=None, pkgs=None, version=None, extra_uninstall_flags=None, **kwargs):
    '''
    Remove packages.

    name
        The name of the package to be deleted.

    version
        The version of the package to be deleted. If this option is used in
        combination with the ``pkgs`` option below, then this version will be
        applied to all targeted packages.

    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    pkg_params = __salt__['pkg_resource.parse_targets'](name,
                                                        pkgs,
                                                        **kwargs)[0]
    old = list_pkgs()
    for target in pkg_params:
        pkginfo = _get_package_info(target)
        if not pkginfo:
            log.error('Unable to locate package {0}'.format(name))
            continue
        if not version:
            version = _get_latest_pkg_version(pkginfo)

        uninstaller = pkginfo[version].get('uninstaller')
        if not uninstaller:
            uninstaller = pkginfo[version].get('installer')
        if not uninstaller:
            return 'Error: No installer or uninstaller configured for package {0}'.format(name)
        if uninstaller.startswith('salt:'):
            cached_pkg = \
                __salt__['cp.is_cached'](uninstaller)
            if not cached_pkg:
                # It's not cached. Cache it, mate.
                cached_pkg = \
                    __salt__['cp.cache_file'](uninstaller)
        else:
            cached_pkg = uninstaller
        cached_pkg = cached_pkg.replace('/', '\\')
        if not os.path.exists(os.path.expandvars(cached_pkg)) \
                and '(x86)' in cached_pkg:
            cached_pkg = cached_pkg.replace('(x86)', '')

        expanded_cached_pkg = str(os.path.expandvars(cached_pkg))
        uninstall_flags = str(pkginfo[version].get('uninstall_flags', ''))

        cmd = []
        if pkginfo[version].get('msiexec'):
            cmd.extend(['msiexec', '/x'])
        cmd.append(expanded_cached_pkg)
        cmd.extend(uninstall_flags.split())
        if extra_uninstall_flags:
            cmd.extend(str(extra_uninstall_flags).split())

        __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)

    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def purge(name=None, pkgs=None, version=None, **kwargs):
    '''
    Package purges are not supported, this function is identical to
    ``remove()``.

    name
        The name of the package to be deleted.

    version
        The version of the package to be deleted. If this option is used in
        combination with the ``pkgs`` option below, then this version will be
        applied to all targeted packages.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    return remove(name=name, pkgs=pkgs, version=version, **kwargs)


def get_repo_data(saltenv='base'):
    '''
    Returns the cached winrepo data

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.get_repo_data
    '''
    #if 'winrepo.data' in __context__:
    #    return __context__['winrepo.data']
    repocache = __opts__['win_repo_cachefile']
    cached_repo = __salt__['cp.is_cached'](repocache, saltenv)
    if not cached_repo:
        __salt__['pkg.refresh_db']()
    try:
        with salt.utils.fopen(repocache, 'rb') as repofile:
            try:
                repodata = msgpack.loads(repofile.read()) or {}
                #__context__['winrepo.data'] = repodata
                return repodata
            except Exception as exc:
                log.exception(exc)
                return {}
    except IOError as exc:
        log.error('Not able to read repo file')
        log.exception(exc)
        return {}


def _get_name_map():
    '''
    Return a reverse map of full pkg names to the names recognized by winrepo.
    '''
    u_name_map = {}
    name_map = get_repo_data().get('name_map', {})
    for k in name_map.keys():
        u_name_map[k.decode('utf-8')] = name_map[k]
    return u_name_map


def _get_package_info(name):
    '''
    Return package info.
    Returns empty map if package not available
    TODO: Add option for version
    '''
    return get_repo_data().get('repo', {}).get(name, {})


def _reverse_cmp_pkg_versions(pkg1, pkg2):
    '''
    Compare software package versions
    '''
    if LooseVersion(pkg1) > LooseVersion(pkg2):
        return 1
    else:
        return -1


def _get_latest_pkg_version(pkginfo):
    if len(pkginfo) == 1:
        return pkginfo.iterkeys().next()
    return sorted(pkginfo, cmp=_reverse_cmp_pkg_versions).pop()
