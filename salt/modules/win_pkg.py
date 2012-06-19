'''
A module to manage software on Windows
'''
try:
    import pythoncom
    import win32com.client
    import win32api
    import win32con
except ImportError:
    pass

def __virtual__():
    '''
    Set the virtual pkg module if the os is Windows
    '''
    return 'pkg' if __grains__['os'] == 'Windows' else False


def _list_removed(old, new):
    '''
    List the packages which have been removed between the two package objects
    '''
    pkgs = []
    for pkg in old:
        if pkg not in new:
            pkgs.append(pkg)
    return pkgs


def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    return 'Not implemented on Windows yet'


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return 'Not implemented on Windows yet'


def list_upgrades():
    '''
    List all available package upgrades on this system

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    return 'Not implemented on Windows yet'


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


def list_pkgs(*args):
    '''
        List the packages currently installed in a dict::

            {'<package_name>': '<version>'}

        CLI Example::

            salt '*' pkg.list_pkgs
    '''
    pythoncom.CoInitialize()
    if len(args) == 0:
        pkgs = dict(
                   list(_get_reg_software().items()) +
                   list(_get_msi_software().items()))
    else:
        # get package version for each package in *args
        pkgs = {}
        for arg in args:
            pkgs.update(_search_software(arg))
    pythoncom.CoUninitialize()
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
    swbem_services = wmi_service.ConnectServer(this_computer,"root\cimv2")
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
    value_data = ''
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
    return 'Not implemented on Windows yet'


def install(name, refresh=False, **kwargs):
    '''
    Install the passed package

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.install <package name>
    '''
    return 'Not implemented on Windows yet'


def upgrade():
    '''
    Run a full system upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.upgrade
    '''
    return 'Not implemented on Windows yet'


def remove(name):
    '''
    Remove a single package

    Return a list containing the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    return 'Not implemented on Windows yet'


def purge(name):
    '''
    Recursively remove a package and all dependencies which were installed
    with it

    Return a list containing the removed packages.

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    return 'Not implemented on Windows yet'
