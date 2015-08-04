# -*- coding: utf-8 -*-
'''
Manage the registry on Windows.

The read_key and set_key functions will be updated in Boron to reflect proper
registry usage. The registry has three main components. Hives, Keys, and Values.

### Hives
Hives are the main sections of the registry and all begin with the word HKEY.
- HKEY_LOCAL_MACHINE
- HKEY_CURRENT_USER
- HKEY_USER

### Keys
Keys are the folders in the registry. Keys can have many nested subkeys. Keys
can have a value assigned to them under the (Default)

### Values
Values are name/data pairs. There can be many values in a key. The (Default)
value corresponds to the Key, the rest are their own value pairs.

:depends:   - winreg Python module
'''

# TODO: Figure out the exceptions _winreg can raise and properly  catch
#       them instead of a bare except that catches any exception at all

# Import third party libs
try:
    import _winreg
    HAS_WINDOWS_MODULES = True
except ImportError:
    try:
        import winreg as _winreg
        HAS_WINDOWS_MODULES = True
    except ImportError:
        HAS_WINDOWS_MODULES = False

# Import python libs
import logging

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'reg'


class Registry(object):
    '''
    Delay '_winreg' usage until this module is used
    '''
    def __init__(self):
        self.hkeys = {
            "HKEY_CURRENT_USER": _winreg.HKEY_CURRENT_USER,
            "HKEY_LOCAL_MACHINE": _winreg.HKEY_LOCAL_MACHINE,
            "HKEY_USERS": _winreg.HKEY_USERS,
            "HKCU": _winreg.HKEY_CURRENT_USER,
            "HKLM": _winreg.HKEY_LOCAL_MACHINE,
            "HKU": _winreg.HKEY_USERS,
            }

        self.reflection_mask = {
            True: _winreg.KEY_ALL_ACCESS,
            False: _winreg.KEY_ALL_ACCESS | _winreg.KEY_WOW64_64KEY,
            }

        self.vtype = {
            "REG_BINARY": _winreg.REG_BINARY,
            "REG_DWORD": _winreg.REG_DWORD,
            "REG_EXPAND_SZ": _winreg.REG_EXPAND_SZ,
            "REG_MULTI_SZ": _winreg.REG_MULTI_SZ,
            "REG_SZ": _winreg.REG_SZ
        }

        self.vtype_reverse = {
            _winreg.REG_BINARY: "REG_BINARY",
            _winreg.REG_DWORD: "REG_DWORD",
            _winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ",
            _winreg.REG_MULTI_SZ: "REG_MULTI_SZ",
            _winreg.REG_SZ: "REG_SZ"
        }

    def __getattr__(self, k):
        try:
            return self.hkeys[k]
        except KeyError:
            msg = 'No hkey named \'{0}. Try one of {1}\''
            hkeys = ', '.join(self.hkeys)
            raise CommandExecutionError(msg.format(k, hkeys))


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows() and HAS_WINDOWS_MODULES:
        return __virtualname__
    return False


def read_key(hkey, path, key=None):
    '''
    *** Incorrect Usage ***
    The name of this function is misleading and will be changed to reflect
    proper usage in the Boron release of Salt. The path option will be removed
    and the key will be the actual key. See the following issue:

    https://github.com/saltstack/salt/issues/25618

    In order to not break existing state files this function will call the
    read_value function if a key is passed. Key will be passed as the value
    name. If key is not passed, this function will return the default value for
    the key.

    In the Boron release this function will be removed in favor of read_value.
    ***

    Read registry key value

    Returns the first unnamed value (Default) as a string.
    Returns none if first unnamed value is empty.
    Returns False if key not found.

    CLI Example:

    .. code-block:: bash

        salt '*' reg.read_key HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'version'
    '''

    ret = {'hive': hkey,
           'key': path,
           'vdata': None,
           'success': True}

    if key:  # This if statement will be removed in Boron
        salt.utils.warn_until('Boron', 'Use reg.read_value to read a registry '
                                       'value. This functionality will be '
                                       'removed in Salt Boron')
        return read_value(hive=hkey,
                          key=path,
                          vname=key)

    registry = Registry()
    hive = registry.hkeys[hkey]

    try:
        value = _winreg.QueryValue(hive, path)
        if value:
            ret['vdata'] = value
        else:
            ret['vdata'] = None
            ret['comment'] = 'Empty Value'
    except WindowsError as exc:  # pylint: disable=E0602
        log.debug(exc)
        ret['comment'] = '{0}'.format(exc)
        ret['success'] = False

    return ret


def read_value(hive, key, vname=None):
    r'''
    Reads a registry value or the default value for a key.

    :param hive: string
    The name of the hive. Can be one of the following
    - HKEY_LOCAL_MACHINE or HKLM
    - HKEY_CURRENT_USER or HKCU
    - HKEY_USER or HKU

    :param key: string
    The key (looks like a path) to the value name.

    :param vname: string
    The value name. These are the individual name/data pairs under the key. If
    not passed, the key (Default) value will be returned

    :return: dict
    A dictionary containing the passed settings as well as the value_data if
    successful. If unsuccessful, sets success to False

    CLI Example:

    .. code-block:: bash

        salt '*' reg.read_value HKEY_LOCAL_MACHINE 'SOFTWARE\Salt' 'version'
    '''

    # Setup the return array
    ret = {'hive': hive,
           'key': key,
           'vname': vname,
           'vdata': None,
           'success': True}

    # If no name is passed, the default value of the key will be returned
    # The value name is Default
    if not vname:
        ret['vname'] = '(Default)'

    registry = Registry()
    hive = registry.hkeys[hive]

    try:
        handle = _winreg.OpenKey(hive, key)
        value, vtype = _winreg.QueryValueEx(handle, vname)
        if value:
            ret['vdata'] = value
            ret['vtype'] = registry.vtype_reverse[vtype]
        else:
            ret['comment'] = 'Empty Value'
    except WindowsError as exc:  # pylint: disable=E0602
        log.debug(exc)
        ret['comment'] = '{0}'.format(exc)
        ret['success'] = False

    return ret


def set_key(hkey, path, value, key=None, vtype='REG_DWORD', reflection=True):
    '''
    *** Incorrect Usage ***
    The name of this function is misleading and will be changed to reflect
    proper usage in the Boron release of Salt. The path option will be removed
    and the key will be the actual key. See the following issue:

    https://github.com/saltstack/salt/issues/25618

    In order to not break existing state files this function will call the
    set_value function if a key is passed. Key will be passed as the value
    name. If key is not passed, this function will return the default value for
    the key.

    In the Boron release this function will be removed in favor of set_value.
    ***

    Set a registry key

    vtype: http://docs.python.org/2/library/_winreg.html#value-types

    CLI Example:

    .. code-block:: bash

        salt '*' reg.set_key HKEY_CURRENT_USER 'SOFTWARE\\Salt' 'version' '0.97' REG_DWORD
    '''

    if key:  # This if statement will be removed in Boron
        salt.utils.warn_until('Boron', 'Use reg.set_value to set a registry '
                                       'value. This functionality will be '
                                       'removed in Salt Boron')
        return set_value(hive=hkey,
                         key=path,
                         vname=key,
                         vdata=value,
                         vtype=vtype)

    registry = Registry()
    hive = registry.hkeys[hkey]
    vtype = registry.vtype['REG_SZ']

    try:
        _winreg.SetValue(hive, path, vtype, value)
        return True
    except WindowsError as exc:  # pylint: disable=E0602
        log.error(exc)
        return False


def set_value(hive, key, vname=None, vdata=None, vtype='REG_SZ', reflection=True):
    '''
    Sets a registry value.

    :param hive: string
    The name of the hive. Can be one of the following
    - HKEY_LOCAL_MACHINE or HKLM
    - HKEY_CURRENT_USER or HKCU
    - HKEY_USER or HKU

    :param key: string
    The key (looks like a path) to the value name.

    :param vname: string
    The value name. These are the individual name/data pairs under the key. If
    not passed, the key (Default) value will be set.

    :param vdata: string
    The value data to be set.

    :param vtype: string
    The value type. Can be one of the following:
    - REG_BINARY
    - REG_DWORD
    - REG_EXPAND_SZ
    - REG_MULTI_SZ
    - REG_SZ

    :param reflection: boolean
    A boolean value indicating that the value should also be set in the
    Wow6432Node portion of the registry. Only applies to 64 bit Windows. This
    setting is ignored for 32 bit Windows.

    :return: boolean
    Returns True if successful, False if not

    CLI Example:

    .. code-block:: bash

        salt '*' reg.set_value HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'version' '2015.5.2'
    '''
    registry = Registry()
    hive = registry.hkeys[hive]
    vtype = registry.vtype[vtype]
    access_mask = registry.reflection_mask[reflection]

    try:
        handle = _winreg.CreateKeyEx(hive, key, 0, access_mask)
        _winreg.SetValueEx(handle, vname, 0, vtype, vdata)
        _winreg.CloseKey(handle)
        return True
    except WindowsError as exc:  # pylint: disable=E0602
        log.error(exc)
        return False


def create_key(hkey, path, key=None, value=None, reflection=True):
    '''
    *** Incorrect Usage ***
    The name of this function is misleading and will be changed to reflect
    proper usage in the Boron release of Salt. The path option will be removed
    and the key will be the actual key. See the following issue:

    https://github.com/saltstack/salt/issues/25618

    In order to not break existing state files this function will call the
    set_value function if key is passed. Key will be passed as the value name.
    If key is not passed, this function will return the default value for the
    key.

    In the Boron release path will be removed and key will be the path. You will
    not pass value.
    ***

    Create a registry key

    CLI Example:

    .. code-block:: bash

        salt '*' reg.create_key HKEY_CURRENT_USER 'SOFTWARE\\Salt' 'version' '0.97'
    '''
    if key:  # This if statement will be removed in Boron
        salt.utils.warn_until('Boron', 'Use reg.set_value to set a registry '
                                       'value. This functionality will be '
                                       'removed in Salt Boron')
        return set_value(hive=hkey,
                         key=path,
                         vname=key,
                         vdata=value,
                         vtype='REG_SZ')

    registry = Registry()
    hive = registry.hkeys[hkey]
    key = path
    access_mask = registry.reflection_mask[reflection]

    try:
        handle = _winreg.CreateKeyEx(hive, key, 0, access_mask)
        _winreg.CloseKey(handle)
        return True
    except WindowsError as exc:  # pylint: disable=E0602
        log.error(exc)
        return False


def delete_key(hkey, path, key=None, reflection=True):
    '''
    *** Incorrect Usage ***
    The name of this function is misleading and will be changed to reflect
    proper usage in the Boron release of Salt. The path option will be removed
    and the key will be the actual key. See the following issue:

    https://github.com/saltstack/salt/issues/25618

    In order to not break existing state files this function will call the
    delete_value function if a key is passed. Key will be passed as the value
    name. If key is not passed, this function will return the default value for
    the key.

    In the Boron release path will be removed and key will be the path.
    reflection will also be removed.
    ***

    Delete a registry key

    Note: This cannot delete a key with subkeys

    CLI Example:

    .. code-block:: bash

        salt '*' reg.delete_key HKEY_CURRENT_USER 'SOFTWARE\\Salt'
    '''

    if key:  # This if statement will be removed in Boron
        salt.utils.warn_until('Boron', 'Use reg.set_value to set a registry '
                                       'value. This functionality will be '
                                       'removed in Salt Boron')
        return delete_value(hive=hkey,
                            key=path,
                            vname=key,
                            reflection=reflection)

    registry = Registry()
    hive = registry.hkeys[hkey]
    key = path

    try:
        _winreg.DeleteKey(hive, key)
        return True
    except WindowsError as exc:  # pylint: disable=E0602
        log.error(exc)
        return False


def delete_value(hive, key, vname=None, reflection=True):
    '''
    Deletes a registry value.

    :param hive: string
    The name of the hive. Can be one of the following
    - HKEY_LOCAL_MACHINE or HKLM
    - HKEY_CURRENT_USER or HKCU
    - HKEY_USER or HKU

    :param key: string
    The key (looks like a path) to the value name.

    :param vname: string
    The value name. These are the individual name/data pairs under the key. If
    not passed, the key (Default) value will be deleted.

    :param reflection: boolean
    A boolean value indicating that the value should also be set in the
    Wow6432Node portion of the registry. Only applies to 64 bit Windows. This
    setting is ignored for 32 bit Windows.

    :return: boolean
    Returns True if successful, False if not

    CLI Example:

    .. code-block:: bash

        salt '*' reg.delete_value HKEY_CURRENT_USER 'SOFTWARE\\Salt' 'version'
    '''
    registry = Registry()
    hive = registry.hkeys[hive]
    access_mask = registry.reflection_mask[reflection]

    try:
        handle = _winreg.OpenKey(hive, key, 0, access_mask)
        _winreg.DeleteValue(handle, vname)
        _winreg.CloseKey(handle)
        return True
    except WindowsError as exc:  # pylint: disable=E0602
        _winreg.CloseKey(handle)
        log.error(exc)
        return False
