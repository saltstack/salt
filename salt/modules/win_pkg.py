'''
A module to manage software on Windows

:depends:   - pythoncom
            - win32com
            - win32con
            - win32api
            - pywintypes
'''

# Import third party libs
try:
    import pythoncom
    import win32com.client
    import win32api
    import win32con
    import pywintypes
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

# Import python libs
import copy
import logging
import msgpack
import os
import locale
from distutils.version import LooseVersion

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Set the virtual pkg module if the os is Windows
    '''
    if salt.utils.is_windows() and HAS_DEPENDENCIES:
        return 'pkg'
    return False


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example::

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...

    '''
    if len(names) == 0:
        return ''
    ret = {}
    pkgs = list_pkgs()
    for name in names:
        candidate = '0'
        version_num = '0'
        pkginfo = _get_package_info(name)
        if not pkginfo:
            # pkg not available in repo, skip
            continue
        if len(pkginfo) == 1:
            candidate = pkginfo.keys()[0]
            name = pkginfo[candidate]['full_name']
            ret[name] = ''
            if name in pkgs:
                version_num = pkgs[name]
            if __salt__['pkg.compare'](pkg1=str(candidate), oper='>',
                                       pkg2=str(version_num)):
                ret[name] = candidate
            continue
        for ver in pkginfo.keys():
            if __salt__['pkg.compare'](pkg1=str(ver), oper='>',
                                       pkg2=str(candidate)):
                candidate = ver
        name = pkginfo[candidate]['full_name']
        ret[name] = ''
        if name in pkgs:
            version_num = pkgs[name]
        if __salt__['pkg.compare'](pkg1=str(candidate), oper='>',
                                   pkg2=str(version_num)):
            ret[name] = candidate
    return ret

# available_version is being deprecated
available_version = latest_version


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    log.warning('pkg.upgrade_available not implemented on Windows yet')
    return False


def list_upgrades(refresh=True):
    '''
    List all available package upgrades on this system

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    log.warning('pkg.list_upgrades not implemented on Windows yet')

    # Uncomment the below once pkg.list_upgrades has been implemented

    #if salt.utils.is_true(refresh):
    #    refresh_db()
    return {}


def list_available(*names):
    '''
    Return a list of available versions of the specified package.

    CLI Example::

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
    if len(names) > 1:
        versions = {}
        for name in names:
            pkginfo = _get_package_info(name)
            if not pkginfo:
                continue
            versions[name] = pkginfo.keys() if pkginfo else []
    return versions


def version(*names, **kwargs):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example::

        salt '*' pkg.version <package name>
    '''
    win_names = []
    ret = {}
    if len(names) == 1:
        versions = _get_package_info(names[0])
        if versions:
            for val in versions.itervalues():
                if 'full_name' in val and len(val.get('full_name', '')) > 0:
                    win_names.append(val.get('full_name', ''))
        nums = __salt__['pkg_resource.version'](*win_names, **kwargs)
        if len(nums):
            for num, val in nums.iteritems():
                if len(val) > 0:
                    return val
        return ''
    if len(names) > 1:
        reverse_dict = {}
        for name in names:
            ret[name] = ''
            versions = _get_package_info(name)
            if versions:
                for val in versions.itervalues():
                    if 'full_name' in val and len(val.get('full_name', '')) > 0:
                        reverse_dict[val.get('full_name', '')] = name
                        win_names.append(val.get('full_name', ''))
        nums = __salt__['pkg_resource.version'](*win_names, **kwargs)
        if len(nums):
            for num, val in nums.iteritems():
                if len(val) > 0:
                    ret[reverse_dict[num]] = val
            return ret
        return ''
    return ret


def list_pkgs(versions_as_list=False, **kwargs):
    '''
        List the packages currently installed in a dict::

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
    with salt.utils.winapi.Com():
        for key, val in _get_reg_software().iteritems():
            __salt__['pkg_resource.add_pkg'](ret, key, val)
        for key, val in _get_msi_software().iteritems():
            __salt__['pkg_resource.add_pkg'](ret, key, val)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
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
    software = dict(
        list(_get_reg_software().items()) +
        list(_get_msi_software().items()))
    for key, value in software.items():
        if key is not None:
            if target.lower() in key.lower():
                search_results[key] = value
    return search_results


def _get_msi_software():
    '''
    This searches the msi product databases and returns a dict keyed
    on the product name and all the product properties in another dict
    '''
    win32_products = {}
    this_computer = "."
    wmi_service = win32com.client.Dispatch("WbemScripting.SWbemLocator")
    swbem_services = wmi_service.ConnectServer(this_computer, "root\\cimv2")

    # Find out whether the Windows Installer provider is present. It
    # is optional on Windows Server 2003 and 64-bit operating systems See
    # http://msdn.microsoft.com/en-us/library/windows/desktop/aa392726%28v=vs.85%29.aspx#windows_installer_provider
    try:
        swbem_services.Get("Win32_Product")
    except pywintypes.com_error:
        log.warning("Windows Installer (MSI) provider not found; package management will not work correctly on MSI packages")
        return win32_products

    products = swbem_services.ExecQuery("Select * from Win32_Product")
    for product in products:
        try:
            prd_name = product.Name.encode('ascii', 'ignore')
            prd_ver = product.Version.encode('ascii', 'ignore')
            win32_products[prd_name] = prd_ver
        except Exception:
            pass
    return win32_products


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
    reg_entries = dict(list(_get_user_keys().items()) +
                       list(_get_machine_keys().items()))
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
                if name[0] == '{':
                    break
                prd_uninst_key = "\\".join([reg_key, name])
                #These reg values aren't guaranteed to exist
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


def _get_user_keys():
    '''
    This will return the hive 'const' value and some registry keys where
    installed software information has been known to exist for the
    HKEY_USERS hive
    '''
    user_hive_and_keys = {}
    user_keys = []
    users_hive = win32con.HKEY_USERS
    #skip some built in and default users since software information in these
    #keys is limited
    skip_users = ['.DEFAULT',
                  'S-1-5-18',
                  'S-1-5-19',
                  'S-1-5-20']
    sw_uninst_key = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall"
    reg_handle = win32api.RegOpenKeyEx(
        users_hive,
        '',
        0,
        win32con.KEY_READ)
    for name, num, blank, time in win32api.RegEnumKeyEx(reg_handle):
        #this is some identical key of a sid that contains some software names
        #but no detailed information about the software installed for that user
        if '_Classes' in name:
            break
        if name not in skip_users:
            usr_sw_uninst_key = "\\".join([name, sw_uninst_key])
            user_keys.append(usr_sw_uninst_key)
    user_hive_and_keys[users_hive] = user_keys
    return user_hive_and_keys


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


def refresh_db():
    '''
    Just recheck the repository and return a dict::

        {'<database name>': Bool}

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    repocache = __opts__['win_repo_cachefile']
    cached_repo = __salt__['cp.is_cached'](repocache)
    if not cached_repo:
        # It's not cached. Cache it, mate.
        cached_repo = __salt__['cp.cache_file'](repocache)
        return True
    # Check if the master's cache file has changed
    if __salt__['cp.hash_file'](repocache) != __salt__['cp.hash_file'](cached_repo):
        cached_repo = __salt__['cp.cache_file'](repocache)
    return True


def install(name=None, refresh=False, **kwargs):
    '''
    Install the passed package

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkg.install <package name>
    '''
    if refresh:
        refresh_db()
    old = list_pkgs()
    pkginfo = _get_package_info(name)
    if not pkginfo:
        return 'Error: Unable to locate package {0}'.format(name)
    for pkg in pkginfo.keys():
        if pkginfo[pkg]['full_name'] in old:
            return '{0} already installed'.format(pkginfo[pkg]['full_name'])
    if kwargs.get('version') is not None:
        version_num = kwargs['version']
    else:
        version_num = _get_latest_pkg_version(pkginfo)
    installer = pkginfo[version_num].get('installer')
    if not installer:
        return 'Error: No installer configured for package {0}'.format(name)
    if installer.startswith('salt:') or installer.startswith('http:') or installer.startswith('https:') or installer.startswith('ftp:'):
        cached_pkg = __salt__['cp.is_cached'](installer)
        if not cached_pkg:
            # It's not cached. Cache it, mate.
            cached_pkg = \
                __salt__['cp.cache_file'](installer)
    else:
        cached_pkg = installer
    cached_pkg = cached_pkg.replace('/', '\\')
    cmd = '"' + str(cached_pkg) + '"' + str(pkginfo[version_num]['install_flags'])
    if pkginfo[version_num].get('msiexec'):
        cmd = 'msiexec /i ' + cmd
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def upgrade(refresh=True):
    '''
    Run a full system upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkg.upgrade
    '''
    log.warning('pkg.upgrade not implemented on Windows yet')

    # Uncomment the below once pkg.upgrade has been implemented

    #if salt.utils.is_true(refresh):
    #    refresh_db()
    return {}


def remove(name=None, pkgs=None, version=None, **kwargs):
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


    Returns a dict containing the changes.

    CLI Example::

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
        cmd = '"' + str(os.path.expandvars(
            cached_pkg)) + '"' + str(pkginfo[version].get('uninstall_flags', ''))
        if pkginfo[version].get('msiexec'):
            cmd = 'msiexec /x ' + cmd
        __salt__['cmd.run_all'](cmd)

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


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


    Returns a dict containing the changes.

    CLI Example::

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    return remove(name=name, pkgs=pkgs, version=version, **kwargs)


def _get_package_info(name):
    '''
    Return package info.
    Returns empty map if package not available
    TODO: Add option for version
    '''
    repocache = __opts__['win_repo_cachefile']
    cached_repo = __salt__['cp.is_cached'](repocache)
    if not cached_repo:
        __salt__['pkg.refresh_db']()
    try:
        with salt.utils.fopen(cached_repo, 'r') as repofile:
            try:
                repodata = msgpack.loads(repofile.read()) or {}
            except Exception:
                return ''
    except IOError:
        log.debug('Not able to read repo file')
        return ''
    if not repodata:
        return ''
    if name in repodata:
        return repodata[name]
    else:
        return ''
    return ''


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
        return pkginfo.keys().pop()
    pkgkeys = pkginfo.keys()
    return sorted(pkgkeys, cmp=_reverse_cmp_pkg_versions).pop()


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
