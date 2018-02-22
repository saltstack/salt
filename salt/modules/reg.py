# -*- coding: utf-8 -*-
'''
Manage the Windows registry

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

:depends:   - PyWin32
'''
# When production windows installer is using Python 3, Python 2 code can be removed
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import sys
import logging
from salt.ext.six.moves import range  # pylint: disable=W0622,import-error

# Import third party libs
try:
    import win32gui
    import win32api
    import win32con
    import pywintypes
    HAS_WINDOWS_MODULES = True
except ImportError:
    HAS_WINDOWS_MODULES = False

# Import Salt libs
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

PY2 = sys.version_info[0] == 2
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'reg'


def __virtual__():
    '''
    Only works on Windows systems with the PyWin32
    '''
    if not salt.utils.platform.is_windows():
        return (False, 'reg execution module failed to load: '
                       'The module will only run on Windows systems')

    if not HAS_WINDOWS_MODULES:
        return (False, 'reg execution module failed to load: '
                       'One of the following libraries did not load: '
                       + 'win32gui, win32con, win32api')

    return __virtualname__


def _to_mbcs(vdata):
    '''
    Converts unicode to to current users character encoding. Use this for values
    returned by reg functions
    '''
    return salt.utils.stringutils.to_unicode(vdata, 'mbcs')


def _to_unicode(vdata):
    '''
    Converts from current users character encoding to unicode. Use this for
    parameters being pass to reg functions
    '''
    return salt.utils.stringutils.to_unicode(vdata, 'utf-8')


class Registry(object):  # pylint: disable=R0903
    '''
    Delay usage until this module is used
    '''
    def __init__(self):
        self.hkeys = {
            'HKEY_CURRENT_CONFIG': win32con.HKEY_CURRENT_CONFIG,
            'HKEY_CLASSES_ROOT': win32con.HKEY_CLASSES_ROOT,
            'HKEY_CURRENT_USER':  win32con.HKEY_CURRENT_USER,
            'HKEY_LOCAL_MACHINE': win32con.HKEY_LOCAL_MACHINE,
            'HKEY_USERS': win32con.HKEY_USERS,
            'HKCC': win32con.HKEY_CURRENT_CONFIG,
            'HKCR': win32con.HKEY_CLASSES_ROOT,
            'HKCU': win32con.HKEY_CURRENT_USER,
            'HKLM': win32con.HKEY_LOCAL_MACHINE,
            'HKU':  win32con.HKEY_USERS,
        }
        self.vtype = {
            'REG_BINARY':    win32con.REG_BINARY,
            'REG_DWORD':     win32con.REG_DWORD,
            'REG_EXPAND_SZ': win32con.REG_EXPAND_SZ,
            'REG_MULTI_SZ':  win32con.REG_MULTI_SZ,
            'REG_SZ':        win32con.REG_SZ,
            'REG_QWORD':     win32con.REG_QWORD
        }
        self.opttype = {
            'REG_OPTION_NON_VOLATILE': 0,
            'REG_OPTION_VOLATILE':     1
        }
        # Return Unicode due to from __future__ import unicode_literals
        self.vtype_reverse = {
            win32con.REG_BINARY:    'REG_BINARY',
            win32con.REG_DWORD:     'REG_DWORD',
            win32con.REG_EXPAND_SZ: 'REG_EXPAND_SZ',
            win32con.REG_MULTI_SZ:  'REG_MULTI_SZ',
            win32con.REG_SZ:        'REG_SZ',
            win32con.REG_QWORD:     'REG_QWORD'
        }
        self.opttype_reverse = {
            0: 'REG_OPTION_NON_VOLATILE',
            1: 'REG_OPTION_VOLATILE'
        }
        # delete_key_recursive uses this to check the subkey contains enough \
        # as we do not want to remove all or most of the registry
        self.subkey_slash_check = {
            win32con.HKEY_CURRENT_USER:   0,
            win32con.HKEY_LOCAL_MACHINE:  1,
            win32con.HKEY_USERS:          1,
            win32con.HKEY_CURRENT_CONFIG: 1,
            win32con.HKEY_CLASSES_ROOT:   1
        }

        self.registry_32 = {
            True: win32con.KEY_READ | win32con.KEY_WOW64_32KEY,
            False: win32con.KEY_READ,
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
    local_hive = _to_unicode(hive)
    local_key = _to_unicode(key)

    registry = Registry()
    hkey = registry.hkeys[local_hive]
    access_mask = registry.registry_32[use_32bit_registry]

    try:
        handle = win32api.RegOpenKeyEx(hkey, local_key, 0, access_mask)
        win32api.RegCloseKey(handle)
        return True
    except WindowsError:  # pylint: disable=E0602
        return False


def broadcast_change():
    '''
    Refresh the windows environment.

    Returns (bool): True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' reg.broadcast_change
    '''
    # https://msdn.microsoft.com/en-us/library/windows/desktop/ms644952(v=vs.85).aspx
    _, res = win32gui.SendMessageTimeout(
        win32con.HWND_BROADCAST, win32con.WM_SETTINGCHANGE, 0, 0,
        win32con.SMTO_ABORTIFHUNG, 5000)
    return not bool(res)


def list_keys(hive, key=None, use_32bit_registry=False):
    '''
    Enumerates the subkeys in a registry key or hive.

    :param str hive: The name of the hive. Can be one of the following

        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU
        - HKEY_CLASSES_ROOT or HKCR
        - HKEY_CURRENT_CONFIG or HKCC

    :param str key: The key (looks like a path) to the value name. If a key is
        not passed, the keys under the hive will be returned.

    :param bool use_32bit_registry: Accesses the 32bit portion of the registry
        on 64 bit installations. On 32bit machines this is ignored.

    :return: A list of keys/subkeys under the hive or key.
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' reg.list_keys HKLM 'SOFTWARE'
    '''

    local_hive = _to_unicode(hive)
    local_key = _to_unicode(key)

    registry = Registry()
    hkey = registry.hkeys[local_hive]
    access_mask = registry.registry_32[use_32bit_registry]

    subkeys = []
    try:
        handle = win32api.RegOpenKeyEx(hkey, local_key, 0, access_mask)

        for i in range(win32api.RegQueryInfoKey(handle)[0]):
            subkey = win32api.RegEnumKey(handle, i)
            if PY2:
                subkeys.append(_to_mbcs(subkey))
            else:
                subkeys.append(subkey)

        handle.Close()

    except pywintypes.error:  # pylint: disable=E0602
        log.debug(r'Cannot find key: %s\%s', hive, key, exc_info=True)
        return False, r'Cannot find key: {0}\{1}'.format(hive, key)

    return subkeys


def list_values(hive, key=None, use_32bit_registry=False, include_default=True):
    '''
    Enumerates the values in a registry key or hive.

    :param str hive: The name of the hive. Can be one of the following

        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU
        - HKEY_CLASSES_ROOT or HKCR
        - HKEY_CURRENT_CONFIG or HKCC

    :param str key: The key (looks like a path) to the value name. If a key is
        not passed, the values under the hive will be returned.

    :param bool use_32bit_registry: Accesses the 32bit portion of the registry
        on 64 bit installations. On 32bit machines this is ignored.

    :param bool include_default: Toggle whether to include the '(Default)' value.

    :return: A list of values under the hive or key.
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' reg.list_values HKLM 'SYSTEM\\CurrentControlSet\\Services\\Tcpip'
    '''
    local_hive = _to_unicode(hive)
    local_key = _to_unicode(key)

    registry = Registry()
    hkey = registry.hkeys[local_hive]
    access_mask = registry.registry_32[use_32bit_registry]
    handle = None
    values = list()

    try:
        handle = win32api.RegOpenKeyEx(hkey, local_key, 0, access_mask)

        for i in range(win32api.RegQueryInfoKey(handle)[1]):
            vname, vdata, vtype = win32api.RegEnumValue(handle, i)

            if not vname:
                vname = "(Default)"

            value = {'hive':   local_hive,
                     'key':    local_key,
                     'vname':  _to_mbcs(vname),
                     'vtype':  registry.vtype_reverse[vtype],
                     'success': True}
            # Only convert text types to unicode
            if vtype == win32con.REG_MULTI_SZ:
                value['vdata'] = [_to_mbcs(i) for i in vdata]
            elif vtype in [win32con.REG_SZ, win32con.REG_EXPAND_SZ]:
                value['vdata'] = _to_mbcs(vdata)
            else:
                value['vdata'] = vdata
            values.append(value)
    except pywintypes.error as exc:  # pylint: disable=E0602
        log.debug(r'Cannot find key: %s\%s', hive, key, exc_info=True)
        return False, r'Cannot find key: {0}\{1}'.format(hive, key)
    finally:
        if handle:
            handle.Close()
    return values


def read_value(hive, key, vname=None, use_32bit_registry=False):
    r'''
    Reads a registry value entry or the default value for a key.

    :param str hive: The name of the hive. Can be one of the following

        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU
        - HKEY_CLASSES_ROOT or HKCR
        - HKEY_CURRENT_CONFIG or HKCC

    :param str key: The key (looks like a path) to the value name.

    :param str vname: The value name. These are the individual name/data pairs
       under the key. If not passed, the key (Default) value will be returned

    :param bool use_32bit_registry: Accesses the 32bit portion of the registry
       on 64bit installations. On 32bit machines this is ignored.

    :return: A dictionary containing the passed settings as well as the
       value_data if successful. If unsuccessful, sets success to False.

    :rtype: dict

    If vname is not passed:

    - Returns the first unnamed value (Default) as a string.
    - Returns none if first unnamed value is empty.
    - Returns False if key not found.

    CLI Example:

    .. code-block:: bash

        salt '*' reg.read_value HKEY_LOCAL_MACHINE 'SOFTWARE\Salt' 'version'
    '''
    # If no name is passed, the default value of the key will be returned
    # The value name is Default

    # Setup the return array
    local_hive = _to_unicode(hive)
    local_key = _to_unicode(key)
    local_vname = _to_unicode(vname)

    ret = {'hive':  local_hive,
           'key':   local_key,
           'vname': local_vname,
           'vdata': None,
           'success': True}

    if not vname:
        ret['vname'] = '(Default)'

    registry = Registry()
    hkey = registry.hkeys[local_hive]
    access_mask = registry.registry_32[use_32bit_registry]

    try:
        handle = win32api.RegOpenKeyEx(hkey, local_key, 0, access_mask)
        try:
            # RegQueryValueEx returns and accepts unicode data
            vdata, vtype = win32api.RegQueryValueEx(handle, local_vname)
            if vdata or vdata in [0, '']:
                # Only convert text types to unicode
                ret['vtype'] = registry.vtype_reverse[vtype]
                if vtype == win32con.REG_MULTI_SZ:
                    ret['vdata'] = [_to_mbcs(i) for i in vdata]
                elif vtype in [win32con.REG_SZ, win32con.REG_EXPAND_SZ]:
                    ret['vdata'] = _to_mbcs(vdata)
                else:
                    ret['vdata'] = vdata
            else:
                ret['comment'] = 'Empty Value'
        except WindowsError:  # pylint: disable=E0602
            ret['vdata'] = ('(value not set)')
            ret['vtype'] = 'REG_SZ'
        except pywintypes.error as exc:  # pylint: disable=E0602
            msg = 'Cannot find {0} in {1}\\{2}' \
                  ''.format(local_vname, local_hive, local_key)
            log.trace(exc)
            log.trace(msg)
            ret['comment'] = msg
            ret['success'] = False
    except pywintypes.error as exc:  # pylint: disable=E0602
        msg = 'Cannot find key: {0}\\{1}'.format(local_hive, local_key)
        log.trace(exc)
        log.trace(msg)
        ret['comment'] = msg
        ret['success'] = False
    return ret


def set_value(hive,
              key,
              vname=None,
              vdata=None,
              vtype='REG_SZ',
              use_32bit_registry=False,
              volatile=False):
    '''
    Sets a registry value entry or the default value for a key.

    :param str hive: The name of the hive. Can be one of the following

        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU
        - HKEY_CLASSES_ROOT or HKCR
        - HKEY_CURRENT_CONFIG or HKCC

    :param str key: The key (looks like a path) to the value name.

    :param str vname: The value name. These are the individual name/data pairs
        under the key. If not passed, the key (Default) value will be set.

    :param object vdata: The value data to be set.
        What the type of this parameter
        should be is determined by the value of the vtype
        parameter. The correspondence
        is as follows:

        .. glossary::

           REG_BINARY
               binary data (i.e. str in python version < 3 and bytes in version >=3)
           REG_DWORD
               int
           REG_EXPAND_SZ
               str
           REG_MULTI_SZ
               list of objects of type str
           REG_SZ
               str

    :param str vtype: The value type.
        The possible values of the vtype parameter are indicated
        above in the description of the vdata parameter.

    :param bool use_32bit_registry: Sets the 32bit portion of the registry on
       64bit installations. On 32bit machines this is ignored.

    :param bool volatile: When this parameter has a value of True, the registry key will be
       made volatile (i.e. it will not persist beyond a system reset or shutdown).
       This parameter only has an effect when a key is being created and at no
       other time.

    :return: Returns True if successful, False if not
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' reg.set_value HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'version' '2015.5.2'

    This function is strict about the type of vdata. For instance the
    the next example will fail because vtype has a value of REG_SZ and vdata
    has a type of int (as opposed to str as expected).

    CLI Example:

    .. code-block:: bash

        salt '*' reg.set_value HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'version' '2015.5.2' \\
        vtype=REG_SZ vdata=0

    However, this next example where vdata is properly quoted should succeed.

    CLI Example:

    .. code-block:: bash

        salt '*' reg.set_value HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'version' '2015.5.2' \\
        vtype=REG_SZ vdata="'0'"

    An example of using vtype REG_BINARY is as follows:

    CLI Example:

    .. code-block:: bash

        salt '*' reg.set_value HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'version' '2015.5.2' \\
        vtype=REG_BINARY vdata='!!binary d2hhdCdzIHRoZSBwb2ludA=='

    An example of using vtype REG_LIST is as follows:

    CLI Example:

    .. code-block:: bash

        salt '*' reg.set_value HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'version' '2015.5.2' \\
        vtype=REG_LIST vdata='[a,b,c]'
    '''
    local_hive = _to_unicode(hive)
    local_key = _to_unicode(key)
    local_vname = _to_unicode(vname)
    local_vtype = _to_unicode(vtype)

    registry = Registry()
    hkey = registry.hkeys[local_hive]
    vtype_value = registry.vtype[local_vtype]
    access_mask = registry.registry_32[use_32bit_registry] | win32con.KEY_ALL_ACCESS

    # Check data type and cast to expected type
    # int will automatically become long on 64bit numbers
    # https://www.python.org/dev/peps/pep-0237/

    # String Types to Unicode
    if vtype_value in [1, 2]:
        local_vdata = _to_unicode(vdata)
    # Don't touch binary...
    elif vtype_value == 3:
        local_vdata = vdata
    # Make sure REG_MULTI_SZ is a list of strings
    elif vtype_value == 7:
        local_vdata = [_to_unicode(i) for i in vdata]
    # Everything else is int
    else:
        local_vdata = int(vdata)

    if volatile:
        create_options = registry.opttype['REG_OPTION_VOLATILE']
    else:
        create_options = registry.opttype['REG_OPTION_NON_VOLATILE']

    try:
        handle, _ = win32api.RegCreateKeyEx(hkey, local_key, access_mask,
                                   Options=create_options)
        win32api.RegSetValueEx(handle, local_vname, 0, vtype_value, local_vdata)
        win32api.RegFlushKey(handle)
        win32api.RegCloseKey(handle)
        broadcast_change()
        return True
    except (win32api.error, SystemError, ValueError, TypeError):  # pylint: disable=E0602
        log.exception('Encountered error setting registry value')
        return False


def delete_key_recursive(hive, key, use_32bit_registry=False):
    '''
    .. versionadded:: 2015.5.4

    Delete a registry key to include all subkeys.

    :param hive: The name of the hive. Can be one of the following

        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU
        - HKEY_CLASSES_ROOT or HKCR
        - HKEY_CURRENT_CONFIG or HKCC

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

    local_hive = _to_unicode(hive)
    local_key = _to_unicode(key)

    # Instantiate the registry object
    registry = Registry()
    hkey = registry.hkeys[local_hive]
    key_path = local_key
    access_mask = registry.registry_32[use_32bit_registry] | win32con.KEY_ALL_ACCESS

    if not _key_exists(local_hive, local_key, use_32bit_registry):
        return False

    if (len(key) > 1) and (key.count('\\', 1) < registry.subkey_slash_check[hkey]):
        log.error(
            'Hive:%s Key:%s; key is too close to root, not safe to remove',
            hive, key
        )
        return False

    # Functions for traversing the registry tree
    def _subkeys(_key):
        '''
        Enumerate keys
        '''
        i = 0
        while True:
            try:
                subkey = win32api.RegEnumKey(_key, i)
                yield subkey
                i += 1
            except pywintypes.error:  # pylint: disable=E0602
                break

    def _traverse_registry_tree(_hkey, _keypath, _ret, _access_mask):
        '''
        Traverse the registry tree i.e. dive into the tree
        '''
        _key = win32api.RegOpenKeyEx(_hkey, _keypath, 0, _access_mask)
        for subkeyname in _subkeys(_key):
            subkeypath = r'{0}\{1}'.format(_keypath, subkeyname)
            _ret = _traverse_registry_tree(_hkey, subkeypath, _ret, access_mask)
            _ret.append(subkeypath)
        return _ret

    # Get a reverse list of registry keys to be deleted
    key_list = []
    key_list = _traverse_registry_tree(hkey, key_path, key_list, access_mask)
    # Add the top level key last, all subkeys must be deleted first
    key_list.append(key_path)

    ret = {'Deleted': [],
           'Failed': []}

    # Delete all sub_keys
    for sub_key_path in key_list:
        try:
            key_handle = win32api.RegOpenKeyEx(hkey, sub_key_path, 0, access_mask)
            win32api.RegDeleteKey(key_handle, '')
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
        - HKEY_CLASSES_ROOT or HKCR
        - HKEY_CURRENT_CONFIG or HKCC

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

    local_hive = _to_unicode(hive)
    local_key = _to_unicode(key)
    local_vname = _to_unicode(vname)

    registry = Registry()
    hkey = registry.hkeys[local_hive]
    access_mask = registry.registry_32[use_32bit_registry] | win32con.KEY_ALL_ACCESS

    try:
        handle = win32api.RegOpenKeyEx(hkey, local_key, 0, access_mask)
        win32api.RegDeleteValue(handle, local_vname)
        win32api.RegCloseKey(handle)
        broadcast_change()
        return True
    except WindowsError as exc:  # pylint: disable=E0602
        log.error(exc, exc_info=True)
        log.error('Hive: %s', local_hive)
        log.error('Key: %s', local_key)
        log.error('ValueName: %s', local_vname)
        log.error('32bit Reg: %s', use_32bit_registry)
        return False


def import_file(source, use_32bit_registry=False):
    '''
    Import registry settings from a Windows ``REG`` file by invoking ``REG.EXE``.

    .. versionadded:: 2018.3.0

    Usage:

    CLI Example:

    .. code-block:: bash

        salt machine1 reg.import_file salt://win/printer_config/110_Canon/postinstall_config.reg

    :param str source: The full path of the ``REG`` file. This
        can be either a local file path or a URL type supported by salt
        (e.g. ``salt://salt_master_path``).

    :param bool use_32bit_registry: If the value of this paramater is ``True``
        then the ``REG`` file will be imported into the Windows 32 bit registry.
        Otherwise the Windows 64 bit registry will be used.

    :return: If the value of ``source`` is an invalid path or otherwise
       causes ``cp.cache_file`` to return ``False`` then
       the function will not return and
       a ``ValueError`` exception will be raised.
       If ``reg.exe`` exits with a non-0 exit code, then
       a ``CommandExecutionError`` exception will be
       raised. On success this function will return
       ``True``.

    :rtype: bool

    '''
    cache_path = __salt__['cp.cache_file'](source)
    if not cache_path:
        error_msg = "File/URL '{0}' probably invalid.".format(source)
        raise ValueError(error_msg)
    if use_32bit_registry:
        word_sz_txt = "32"
    else:
        word_sz_txt = "64"
    cmd = 'reg import "{0}" /reg:{1}'.format(cache_path, word_sz_txt)
    cmd_ret_dict = __salt__['cmd.run_all'](cmd, python_shell=True)
    retcode = cmd_ret_dict['retcode']
    if retcode != 0:
        raise CommandExecutionError(
            'reg.exe import failed',
            info=cmd_ret_dict
        )
    return True
