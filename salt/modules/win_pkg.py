'''
A module to manage software on Windows

:depends:   - pythoncom
            - win32com
            - win32con
            - win32api
'''

# Import third party libs
try:
    import pythoncom
    import win32com.client
    import win32api
    import win32con
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

# Import python libs
import logging
import msgpack
import os
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


def _list_removed(old, new):
    '''
    List the packages which have been removed between the two package objects
    '''
    pkgs = []
    for pkg in old:
        if pkg not in new:
            pkgs.append(pkg)
    return pkgs


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
        version = '0'
        pkginfo = _get_package_info(name)
        if not pkginfo:
            # pkg not available in repo, skip
            continue
        if len(pkginfo) == 1:
            candidate = pkginfo.keys()[0]
            name = pkginfo[candidate]['full_name']
            ret[name] = ''
            if name in pkgs:
                version = pkgs[name]
            if __salt__['pkg_resource.perform_cmp'](str(candidate),
                                                    str(version)) > 0:
                ret[name] = candidate
            continue
        for ver in pkginfo.keys():
            if __salt__['pkg_resource.perform_cmp'](str(ver), str(candidate)) > 0:
                candidate = ver
        name = pkginfo[candidate]['full_name']
        ret[name] = ''
        if name in pkgs:
            version = pkgs[name]
        if __salt__['pkg_resource.perform_cmp'](str(candidate),
                                                str(version)) > 0:
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


def version(*names, **kwargs):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example::

        salt '*' pkg.version <package name>
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def list_pkgs(*args, **kwargs):
    '''
        List the packages currently installed in a dict::

            {'<package_name>': '<version>'}

        CLI Example::

            salt '*' pkg.list_pkgs
    '''
    versions_as_list = \
        salt.utils.is_true(kwargs.get('versions_as_list'))
    pkgs = {}
    with salt.utils.winapi.Com():
        if len(args) == 0:
            for key, val in _get_reg_software().iteritems():
                __salt__['pkg_resource.add_pkg'](pkgs, key, val)
            for key, val in _get_msi_software().iteritems():
                __salt__['pkg_resource.add_pkg'](pkgs, key, val)
        else:
            # get package version for each package in *args
            for arg in args:
                for key, val in _search_software(arg).iteritems():
                    __salt__['pkg_resource.add_pkg'](pkgs, key, val)

    __salt__['pkg_resource.sort_pkglist'](pkgs)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return pkgs


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
    swbem_services = wmi_service.ConnectServer(this_computer, "root\cimv2")
    products = swbem_services.ExecQuery("Select * from Win32_Product")
    for product in products:
        prd_name = product.Name.encode('ascii', 'ignore')
        prd_ver = product.Version.encode('ascii', 'ignore')
        win32_products[prd_name] = prd_ver
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
                prd_ver = _get_reg_value(
                    reg_hive,
                    prd_uninst_key,
                    "DisplayVersion")
                if not name in ignore_list:
                    if not prd_name == 'Not Found':
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
    If 'name' is empty string, reads default value.
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
    if __salt__['cp.hash_file'](repocache) !=\
            __salt__['cp.hash_file'](cached_repo):
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
    for pkg in pkginfo.keys():
        if pkginfo[pkg]['full_name'] in old:
            return '{0} already installed'.format(pkginfo[pkg]['full_name'])
    if kwargs.get('version') is not None:
        version = kwargs['version']
    else:
        version = _get_latest_pkg_version(pkginfo)
    if pkginfo[version]['installer'].startswith('salt:') or pkginfo[version]['installer'].startswith('http:') or pkginfo[version]['installer'].startswith('https:') or pkginfo[version]['installer'].startswith('ftp:'):
        cached_pkg = __salt__['cp.is_cached'](pkginfo[version]['installer'])
        if not cached_pkg:
            # It's not cached. Cache it, mate.
            cached_pkg = __salt__['cp.cache_file'](pkginfo[
                                                   version]['installer'])
    else:
        cached_pkg = pkginfo[version]['installer']
    cached_pkg = cached_pkg.replace('/', '\\')
    cmd = '"' + str(cached_pkg) + '"' + str(pkginfo[version]['install_flags'])
    if pkginfo[version]['msiexec']:
        cmd = 'msiexec /i ' + cmd
    stderr = __salt__['cmd.run_all'](cmd).get('stderr', '')
    if stderr:
        log.error(stderr)
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


def remove(name, version=None, **kwargs):
    '''
    Remove a single package

    Return a list containing the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    old = list_pkgs()
    pkginfo = _get_package_info(name)
    if not version:
        version = _get_latest_pkg_version(pkginfo)

    if pkginfo[version]['uninstaller'].startswith('salt:'):
        cached_pkg = __salt__['cp.is_cached'](pkginfo[version]['uninstaller'])
        if not cached_pkg:
            # It's not cached. Cache it, mate.
            cached_pkg = __salt__['cp.cache_file'](pkginfo[
                                                   version]['uninstaller'])
    else:
        cached_pkg = pkginfo[version]['uninstaller']
    cached_pkg = cached_pkg.replace('/', '\\')
    if not os.path.exists(os.path.expandvars(cached_pkg)) and '(x86)' in cached_pkg:
        cached_pkg = cached_pkg.replace('(x86)', '')
    cmd = '"' + str(os.path.expandvars(
        cached_pkg)) + '"' + str(pkginfo[version]['uninstall_flags'])
    if pkginfo[version]['msiexec']:
        cmd = 'msiexec /x ' + cmd
    stderr = __salt__['cmd.run_all'](cmd).get('stderr', '')
    if stderr:
        log.error(stderr)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def purge(name, version=None, **kwargs):
    '''
    Recursively remove a package and all dependencies which were installed
    with it

    Return a list containing the removed packages.

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    return remove(name, version, **kwargs)


def _get_package_info(name):
    '''
    Return package info.
    Returns empty string if package not available
    TODO: Add option for version
    '''
    repocache = __opts__['win_repo_cachefile']
    cached_repo = __salt__['cp.is_cached'](repocache)
    if not cached_repo:
        __salt__['pkg.refresh_db']
    try:
        with salt.utils.fopen(cached_repo, 'r') as repofile:
            try:
                repodata = msgpack.loads(repofile.read()) or {}
            except:
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
