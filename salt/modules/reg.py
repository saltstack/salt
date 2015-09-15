# -*- coding: utf-8 -*-
'''
===========================
Manage the Windows registry
===========================

The read_key and set_key functions will be updated in Boron to reflect proper
registry usage. The registry has three main components. Hives, Keys, and Values.

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

# TODO: Figure out the exceptions _winreg can raise and properly catch them

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

    return read_value(hive=hkey, key=path)


def read_value(hive, key, vname=None):
    r'''
    Reads a registry value entry or the default value for a key.

    :param str hive:
        The name of the hive. Can be one of the following
        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU

    :param str key:
        The key (looks like a path) to the value name.

    :param str vname:
        The value name. These are the individual name/data pairs under the key.
        If not passed, the key (Default) value will be returned

    :return:
        A dictionary containing the passed settings as well as the value_data if
        successful. If unsuccessful, sets success to False

        If vname is not passed:
        - Returns the first unnamed value (Default) as a string.
        - Returns none if first unnamed value is empty.
        - Returns False if key not found.
    :rtype: dict

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

    try:
        handle = _winreg.OpenKey(hkey, key)
        try:
            vdata, vtype = _winreg.QueryValueEx(handle, vname)
            if vdata or vdata in [0, '']:
                ret['vtype'] = registry.vtype_reverse[vtype]
                ret['vdata'] = vdata
            else:
                ret['comment'] = 'Empty Value'
        except WindowsError as exc:  # pylint: disable=E0602
            ret['vdata'] = ('(value not set)')
            ret['vtype'] = 'REG_SZ'
            ret['success'] = True
    except WindowsError as exc:  # pylint: disable=E0602
        log.debug(exc)
        log.debug('Cannot find key: {0}\\{1}'.format(hive, key))
        ret['comment'] = 'Cannot find key: {0}\\{1}'.format(hive, key)
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

    return set_value(hive=hkey, key=path, vdata=value, vtype=vtype)


def set_value(hive, key, vname=None, vdata=None, vtype='REG_SZ', reflection=True):
    '''
    Sets a registry value entry or the default value for a key.

    :param str hive:
        The name of the hive. Can be one of the following
        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU

    :param str key:
        The key (looks like a path) to the value name.

    :param str vname:
        The value name. These are the individual name/data pairs under the key.
        If not passed, the key (Default) value will be set.

    :param str vdata:
        The value data to be set.

    :param str vtype:
        The value type. Can be one of the following:
        - REG_BINARY
        - REG_DWORD
        - REG_EXPAND_SZ
        - REG_MULTI_SZ
        - REG_SZ

    :param bool reflection:
        A boolean value indicating that the value should also be set in the
        Wow6432Node portion of the registry. Only applies to 64 bit Windows.
        This setting is ignored for 32 bit Windows.

    :return:
        Returns True if successful, False if not
    :rtype: bool

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
    except (WindowsError, ValueError) as exc:  # pylint: disable=E0602
        log.error(exc, exc_info=True)
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
        salt.utils.warn_until('Boron', 'Use reg.set_value to create a registry '
                                       'value. This functionality will be '
                                       'removed in Salt Boron')
        return set_value(hive=hkey,
                         key=path,
                         vname=key,
                         vdata=value,
                         vtype='REG_SZ')

    return set_value(hive=hkey, key=path)


def delete_key(hkey, path, key=None, reflection=True, force=False):
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

    CLI Example:

    .. code-block:: bash

        salt '*' reg.delete_key HKEY_CURRENT_USER 'SOFTWARE\\Salt'

    :param str hkey: (will be changed to hive)
        The name of the hive. Can be one of the following
        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU

    :param str path: (will be changed to key)
        The key (looks like a path) to remove.

    :param str key: (used incorrectly)
        Will be removed in Boron

    :param bool reflection:
        A boolean value indicating that the value should also be removed from
        the Wow6432Node portion of the registry. Only applies to 64 bit Windows.
        This setting is ignored for 32 bit Windows.

        Only applies to delete value. If the key parameter is passed, this
        function calls delete_value instead. Will be changed in Boron.

    :param bool force:
        A boolean value indicating that all subkeys should be removed as well.
        If this is set to False (default) and there are subkeys, the delete_key
        function will fail.

    :return:
        Returns True if successful, False if not
        If force=True, the results of delete_key_recursive are returned.
    :rtype: bool
    '''

    if key:  # This if statement will be removed in Boron
        salt.utils.warn_until('Boron',
                              'Variable names will be changed to match Windows '
                              'Registry terminology. These changes will be '
                              'made in Boron')
        return delete_value(hive=hkey,
                            key=path,
                            vname=key,
                            reflection=reflection)

    if force:
        return delete_key_recursive(hkey, path)

    registry = Registry()
    hive = registry.hkeys[hkey]
    key = path

    try:
        # Can't use delete_value to delete a key
        _winreg.DeleteKey(hive, key)
        return True
    except WindowsError as exc:  # pylint: disable=E0602
        log.error(exc, exc_info=True)
        return False


def delete_key_recursive(hive, key):
    '''
    .. versionadded:: 2015.5.4

    Delete a registry key to include all subkeys.

    :param hive:
        The name of the hive. Can be one of the following
        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU

    :param key:
        The key to remove (looks like a path)

    :return:
        A dictionary listing the keys that deleted successfully as well as those
        that failed to delete.
    :rtype: dict

    The following example will remove ``salt`` and all its subkeys from the
    ``SOFTWARE`` key in ``HKEY_LOCAL_MACHINE``:

    CLI Example:

    .. code-block:: bash

        salt '*' reg.delete_key_recursive HKLM SOFTWARE\\salt
    '''
    # Functions for traversing the registry tree
    def subkeys(key):
        i = 0
        while True:
            try:
                subkey = _winreg.EnumKey(key, i)
                yield subkey
                i += 1
            except WindowsError:  # pylint: disable=E0602
                break

    def traverse_registry_tree(hkey, keypath, ret):
        key = _winreg.OpenKey(hkey, keypath, 0, _winreg.KEY_READ)
        for subkeyname in subkeys(key):
            subkeypath = r'{0}\{1}'.format(keypath, subkeyname)
            ret = traverse_registry_tree(hkey, subkeypath, ret)
            ret.append('{0}'.format(subkeypath))
        return ret

    # Instantiate the registry object
    registry = Registry()
    hkey = registry.hkeys[hive]
    keypath = key

    # Get a reverse list of registry keys to be deleted
    key_list = []
    key_list = traverse_registry_tree(hkey, keypath, key_list)

    ret = {'Deleted': [],
           'Failed': []}

    # Delete all subkeys
    for keypath in key_list:
        try:
            _winreg.DeleteKey(hkey, keypath)
            ret['Deleted'].append(r'{0}\{1}'.format(hive, keypath))
        except WindowsError as exc:  # pylint: disable=E0602
            log.error(exc, exc_info=True)
            ret['Failed'].append(r'{0}\{1} {2}'.format(hive, key, exc))

    # Delete the key now that all the subkeys are deleted
    try:
        _winreg.DeleteKey(hkey, key)
        ret['Deleted'].append(r'{0}\{1}'.format(hive, key))
    except WindowsError as exc:  # pylint: disable=E0602
        log.error(exc, exc_info=True)
        ret['Failed'].append(r'{0}\{1} {2}'.format(hive, key, exc))

    return ret


def delete_value(hive, key, vname=None, reflection=True):
    '''
    Delete a registry value entry or the default value for a key.

    :param str hive:
        The name of the hive. Can be one of the following
        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU

    :param str key:
        The key (looks like a path) to the value name.

    :param str vname:
        The value name. These are the individual name/data pairs under the key.
        If not passed, the key (Default) value will be deleted.

    :param bool reflection:
        A boolean value indicating that the value should also be set in the
        Wow6432Node portion of the registry. Only applies to 64 bit Windows.
        This setting is ignored for 32 bit Windows.

    :return:
        Returns True if successful, False if not
    :rtype: bool

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
        log.error(exc, exc_info=True)
        return False
