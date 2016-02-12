# -*- coding: utf-8 -*-
'''
===========================
Manage the Windows registry
===========================

-----
Hives
-----
Hives are the main sections of the registry and all begin with the word HKEY.
- HKEY_LOCAL_MACHINE
- HKEY_CURRENT_USER
- HKEY_USER

----
Keys
----
Keys are the folders in the registry. Keys can have many nested subkeys. Keys
can have a value assigned to them under the (Default)

-----------------
Values or Entries
-----------------
Values/Entries are name/data pairs. There can be many values in a key. The
(Default) value corresponds to the Key, the rest are their own value pairs.

:depends:   - winreg Python module
'''
# Import python libs
from __future__ import absolute_import
import logging

# Import third party libs
try:
    from salt.ext.six.moves import winreg as _winreg  # pylint: disable=import-error,no-name-in-module
    from win32gui import SendMessageTimeout
    from win32con import HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG
    HAS_WINDOWS_MODULES = True
except ImportError:
    HAS_WINDOWS_MODULES = False

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'reg'


def __virtual__():
    '''
    Only works on Windows systems with the _winreg python module
    '''
    if not salt.utils.is_windows():
        return (False, 'reg execution module failed to load: '
                       'The module will only run on Windows systems')

    if not HAS_WINDOWS_MODULES:
        return (False, 'reg execution module failed to load: '
                       'The _winreg python library could not be loaded')

    return __virtualname__


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

        self.registry_32 = {
            True: _winreg.KEY_ALL_ACCESS | _winreg.KEY_WOW64_32KEY,
            False: _winreg.KEY_ALL_ACCESS,
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


def _key_exists(hive, key, use_32bit_registry=False):
    '''
    Check that the key is found in the registry

    :param str hive: The hive to connect to.
    :param str key: The key to check
    :param bool use_32bit_registry: Look in the 32bit portion of the registry

    :return: Returns True if found, False if not found
    :rtype: bool
    '''
    registry = Registry()
    hkey = registry.hkeys[hive]
    access_mask = registry.registry_32[use_32bit_registry]

    try:
        handle = _winreg.OpenKey(hkey, key, 0, access_mask)
        _winreg.CloseKey(handle)
        return True
    except WindowsError:  # pylint: disable=E0602
        return False


def broadcast_change():
    '''
    Refresh the windows environment.
    '''
    # https://msdn.microsoft.com/en-us/library/windows/desktop/ms644952(v=vs.85).aspx
    SendMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0, 0,
                       SMTO_ABORTIFHUNG, 5000)


def read_value(hive, key, vname=None, use_32bit_registry=False):
    r'''
    Reads a registry value entry or the default value for a key.

    :param str hive: The name of the hive. Can be one of the following

        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU

    :param str key: The key (looks like a path) to the value name.

    :param str vname: The value name. These are the individual name/data pairs
    under the key. If not passed, the key (Default) value will be returned

    :param bool use_32bit_registry: Accesses the 32bit portion of the registry
    on 64bit installations. On 32bit machines this is ignored.

    :return: A dictionary containing the passed settings as well as the
    value_data if successful. If unsuccessful, sets success to False
    :rtype: dict

    If vname is not passed:

    - Returns the first unnamed value (Default) as a string.
    - Returns none if first unnamed value is empty.
    - Returns False if key not found.

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
    hkey = registry.hkeys[hive]
    access_mask = registry.registry_32[use_32bit_registry]

    try:
        handle = _winreg.OpenKey(hkey, key, 0, access_mask)
        try:
            vdata, vtype = _winreg.QueryValueEx(handle, vname)
            if vdata or vdata in [0, '']:
                ret['vtype'] = registry.vtype_reverse[vtype]
                ret['vdata'] = vdata
            else:
                ret['comment'] = 'Empty Value'
        except WindowsError:  # pylint: disable=E0602
            ret['vdata'] = ('(value not set)')
            ret['vtype'] = 'REG_SZ'
    except WindowsError as exc:  # pylint: disable=E0602
        log.debug(exc)
        log.debug('Cannot find key: {0}\\{1}'.format(hive, key))
        ret['comment'] = 'Cannot find key: {0}\\{1}'.format(hive, key)
        ret['success'] = False

    return ret


def set_value(hive,
              key,
              vname=None,
              vdata=None,
              vtype='REG_SZ',
              use_32bit_registry=False):
    '''
    Sets a registry value entry or the default value for a key.

    :param str hive: The name of the hive. Can be one of the following

        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU

    :param str key: The key (looks like a path) to the value name.

    :param str vname: The value name. These are the individual name/data pairs
    under the key. If not passed, the key (Default) value will be set.

    :param str vdata: The value data to be set.

    :param str vtype: The value type. Can be one of the following:

        - REG_BINARY
        - REG_DWORD
        - REG_EXPAND_SZ
        - REG_MULTI_SZ
        - REG_SZ

    :param bool use_32bit_registry: Sets the 32bit portion of the registry on
    64bit installations. On 32bit machines this is ignored.

    :return: Returns True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' reg.set_value HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'version' '2015.5.2'
    '''
    registry = Registry()
    hkey = registry.hkeys[hive]
    vtype = registry.vtype[vtype]
    access_mask = registry.registry_32[use_32bit_registry]

    try:
        handle = _winreg.CreateKeyEx(hkey, key, 0, access_mask)
        if vtype == registry.vtype['REG_SZ']\
                or vtype == registry.vtype['REG_BINARY']:
            vdata = str(vdata)
        _winreg.SetValueEx(handle, vname, 0, vtype, vdata)
        _winreg.FlushKey(handle)
        _winreg.CloseKey(handle)
        broadcast_change()
        return True
    except (WindowsError, ValueError, TypeError) as exc:  # pylint: disable=E0602
        log.error(exc, exc_info=True)
        return False


def delete_key_recursive(hive, key, use_32bit_registry=False):
    '''
    .. versionadded:: 2015.5.4

    Delete a registry key to include all subkeys.

    :param hive: The name of the hive. Can be one of the following

        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU

    :param key: The key to remove (looks like a path)

    :param bool use_32bit_registry: Deletes the 32bit portion of the registry on
    64bit installations. On 32bit machines this is ignored.

    :return: A dictionary listing the keys that deleted successfully as well as
    those that failed to delete.
    :rtype: dict

    The following example will remove ``salt`` and all its subkeys from the
    ``SOFTWARE`` key in ``HKEY_LOCAL_MACHINE``:

    CLI Example:

    .. code-block:: bash

        salt '*' reg.delete_key_recursive HKLM SOFTWARE\\salt
    '''
    # Instantiate the registry object
    registry = Registry()
    hkey = registry.hkeys[hive]
    key_path = key
    access_mask = registry.registry_32[use_32bit_registry]

    if not _key_exists(hive, key, use_32bit_registry):
        return False

    # Functions for traversing the registry tree
    def subkeys(_key):
        i = 0
        while True:
            try:
                subkey = _winreg.EnumKey(_key, i)
                yield subkey
                i += 1
            except WindowsError:  # pylint: disable=E0602
                break

    def traverse_registry_tree(_hkey, _keypath, _ret, _access_mask):
        _key = _winreg.OpenKey(_hkey, _keypath, 0, _access_mask)
        for subkeyname in subkeys(_key):
            subkeypath = r'{0}\{1}'.format(_keypath, subkeyname)
            _ret = traverse_registry_tree(_hkey, subkeypath, _ret, access_mask)
            _ret.append('{0}'.format(subkeypath))
        return _ret

    # Get a reverse list of registry keys to be deleted
    key_list = []
    key_list = traverse_registry_tree(hkey, key_path, key_list, access_mask)
    # Add the top level key last, all subkeys must be deleted first
    key_list.append(r'{0}'.format(key_path))

    ret = {'Deleted': [],
           'Failed': []}

    # Delete all sub_keys
    for sub_key_path in key_list:
        try:
            key_handle = _winreg.OpenKey(hkey, sub_key_path, 0, access_mask)
            _winreg.DeleteKey(key_handle, '')
            ret['Deleted'].append(r'{0}\{1}'.format(hive, sub_key_path))
        except WindowsError as exc:  # pylint: disable=E0602
            log.error(exc, exc_info=True)
            ret['Failed'].append(r'{0}\{1} {2}'.format(hive, sub_key_path, exc))

    broadcast_change()

    return ret


def delete_value(hive, key, vname=None, use_32bit_registry=False):
    '''
    Delete a registry value entry or the default value for a key.

    :param str hive: The name of the hive. Can be one of the following

        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU

    :param str key: The key (looks like a path) to the value name.

    :param str vname: The value name. These are the individual name/data pairs
    under the key. If not passed, the key (Default) value will be deleted.

    :param bool use_32bit_registry: Deletes the 32bit portion of the registry on
    64bit installations. On 32bit machines this is ignored.

    :return: Returns True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' reg.delete_value HKEY_CURRENT_USER 'SOFTWARE\\Salt' 'version'
    '''
    registry = Registry()
    h_hive = registry.hkeys[hive]
    access_mask = registry.registry_32[use_32bit_registry]

    try:
        handle = _winreg.OpenKey(h_hive, key, 0, access_mask)
        _winreg.DeleteValue(handle, vname)
        _winreg.CloseKey(handle)
        broadcast_change()
        return True
    except WindowsError as exc:  # pylint: disable=E0602
        log.error(exc, exc_info=True)
        log.error('Hive: {0}'.format(hive))
        log.error('Key: {0}'.format(key))
        log.error('ValueName: {0}'.format(vname))
        log.error('32bit Reg: {0}'.format(use_32bit_registry))
        return False
