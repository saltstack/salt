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
# When production windows installer is using Python 3, Python 2 code can be removed

# Import _future_ python libs first & before any other code
from __future__ import absolute_import
from __future__ import unicode_literals
# Import python libs
import sys
import logging
from salt.ext.six.moves import range  # pylint: disable=W0622,import-error
from salt.ext import six

# Import third party libs
try:
    from salt.ext.six.moves import winreg as _winreg  # pylint: disable=import-error,no-name-in-module
    from win32gui import SendMessageTimeout
    from win32con import HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG
    from win32api import RegCreateKeyEx, RegSetValueEx, RegFlushKey, RegCloseKey, error as win32apiError
    HAS_WINDOWS_MODULES = True
except ImportError:
    HAS_WINDOWS_MODULES = False

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError

PY2 = sys.version_info[0] == 2
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
                       'One of the following libraries did not load: '
                       + '_winreg, win32gui, win32con, win32api')

    return __virtualname__


# winreg in python 2 is hard coded to use codex 'mbcs', which uses
# encoding that the user has assign. The function _unicode_to_mbcs
# and _unicode_to_mbcs help with this.


def _unicode_to_mbcs(instr):
    '''
    Converts unicode to to current users character encoding.
    '''
    if isinstance(instr, six.text_type):
        # unicode to windows utf8
        return instr.encode('mbcs')
    else:
        # Assume its byte str or not a str/unicode
        return instr


def _mbcs_to_unicode(instr):
    '''
    Converts from current users character encoding to unicode.
    When instr has a value of None, the return value of the function
    will also be None.
    '''
    if instr is None or isinstance(instr, six.text_type):
        return instr
    else:
        return six.text_type(instr, 'mbcs')


def _mbcs_to_unicode_wrap(obj, vtype):
    '''
    Wraps _mbcs_to_unicode for use with registry vdata
    '''
    if vtype == 'REG_BINARY':
        # We should be able to leave it alone if the user has passed binary data in yaml with
        # binary !!
        # In python < 3 this should have type str and in python 3+ this should be a byte array
        return obj
    if isinstance(obj, list):
        return [_mbcs_to_unicode(x) for x in obj]
    elif isinstance(obj, int):
        return obj
    else:
        return _mbcs_to_unicode(obj)


class Registry(object):  # pylint: disable=R0903
    '''
    Delay '_winreg' usage until this module is used
    '''
    def __init__(self):
        self.hkeys = {
            'HKEY_CURRENT_USER':  _winreg.HKEY_CURRENT_USER,
            'HKEY_LOCAL_MACHINE': _winreg.HKEY_LOCAL_MACHINE,
            'HKEY_USERS': _winreg.HKEY_USERS,
            'HKCU': _winreg.HKEY_CURRENT_USER,
            'HKLM': _winreg.HKEY_LOCAL_MACHINE,
            'HKU':  _winreg.HKEY_USERS,
        }
        self.vtype = {
            'REG_BINARY':    _winreg.REG_BINARY,
            'REG_DWORD':     _winreg.REG_DWORD,
            'REG_EXPAND_SZ': _winreg.REG_EXPAND_SZ,
            'REG_MULTI_SZ':  _winreg.REG_MULTI_SZ,
            'REG_SZ':        _winreg.REG_SZ
        }
        self.opttype = {
            'REG_OPTION_NON_VOLATILE': _winreg.REG_OPTION_NON_VOLATILE,
            'REG_OPTION_VOLATILE':     _winreg.REG_OPTION_VOLATILE
        }
        # Return Unicode due to from __future__ import unicode_literals
        self.vtype_reverse = {
            _winreg.REG_BINARY:    'REG_BINARY',
            _winreg.REG_DWORD:     'REG_DWORD',
            _winreg.REG_EXPAND_SZ: 'REG_EXPAND_SZ',
            _winreg.REG_MULTI_SZ:  'REG_MULTI_SZ',
            _winreg.REG_SZ:        'REG_SZ'
        }
        self.opttype_reverse = {
            _winreg.REG_OPTION_NON_VOLATILE: 'REG_OPTION_NON_VOLATILE',
            _winreg.REG_OPTION_VOLATILE:     'REG_OPTION_VOLATILE'
        }
        # delete_key_recursive uses this to check the subkey contains enough \
        # as we do not want to remove all or most of the registry
        self.subkey_slash_check = {
            _winreg.HKEY_CURRENT_USER:  0,
            _winreg.HKEY_LOCAL_MACHINE: 1,
            _winreg.HKEY_USERS:         1
        }

        self.registry_32 = {
            True: _winreg.KEY_READ | _winreg.KEY_WOW64_32KEY,
            False: _winreg.KEY_READ,
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

    if PY2:
        local_hive = _mbcs_to_unicode(hive)
        local_key = _unicode_to_mbcs(key)
    else:
        local_hive = hive
        local_key = key

    registry = Registry()
    hkey = registry.hkeys[local_hive]
    access_mask = registry.registry_32[use_32bit_registry]

    try:
        handle = _winreg.OpenKey(hkey, local_key, 0, access_mask)
        _winreg.CloseKey(handle)
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
    _, res = SendMessageTimeout(HWND_BROADCAST, WM_SETTINGCHANGE, 0, 0,
                                SMTO_ABORTIFHUNG, 5000)
    return not bool(res)


def list_keys(hive, key=None, use_32bit_registry=False):
    '''
    Enumerates the subkeys in a registry key or hive.

    :param str hive: The name of the hive. Can be one of the following

        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU

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

    if PY2:
        local_hive = _mbcs_to_unicode(hive)
        local_key = _unicode_to_mbcs(key)
    else:
        local_hive = hive
        local_key = key

    registry = Registry()
    hkey = registry.hkeys[local_hive]
    access_mask = registry.registry_32[use_32bit_registry]

    subkeys = []
    try:
        handle = _winreg.OpenKey(hkey, local_key, 0, access_mask)

        for i in range(_winreg.QueryInfoKey(handle)[0]):
            subkey = _winreg.EnumKey(handle, i)
            if PY2:
                subkeys.append(_mbcs_to_unicode(subkey))
            else:
                subkeys.append(subkey)

        handle.Close()

    except WindowsError as exc:  # pylint: disable=E0602
        log.debug(exc)
        log.debug('Cannot find key: {0}\\{1}'.format(hive, key))
        return False, 'Cannot find key: {0}\\{1}'.format(hive, key)

    return subkeys


def list_values(hive, key=None, use_32bit_registry=False, include_default=True):
    '''
    Enumerates the values in a registry key or hive.

    :param str hive: The name of the hive. Can be one of the following

        - HKEY_LOCAL_MACHINE or HKLM
        - HKEY_CURRENT_USER or HKCU
        - HKEY_USER or HKU

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

    if PY2:
        local_hive = _mbcs_to_unicode(hive)
        local_key = _unicode_to_mbcs(key)
    else:
        local_hive = hive
        local_key = key

    registry = Registry()
    hkey = registry.hkeys[local_hive]
    access_mask = registry.registry_32[use_32bit_registry]
    handle = None
    values = list()

    try:
        handle = _winreg.OpenKey(hkey, local_key, 0, access_mask)

        for i in range(_winreg.QueryInfoKey(handle)[1]):
            vname, vdata, vtype = _winreg.EnumValue(handle, i)

            value = {'hive':   local_hive,
                     'key':    local_key,
                     'vname':  vname,
                     'vdata':  vdata,
                     'vtype':  registry.vtype_reverse[vtype],
                     'success': True}
            values.append(value)
        if include_default:
            # Get the default value for the key
            value = {'hive':    local_hive,
                     'key':     local_key,
                     'vname':   '(Default)',
                     'vdata':   None,
                     'success': True}
            try:
                # QueryValueEx returns unicode data
                vdata, vtype = _winreg.QueryValueEx(handle, '(Default)')
                if vdata or vdata in [0, '']:
                    value['vtype'] = registry.vtype_reverse[vtype]
                    value['vdata'] = vdata
                else:
                    value['comment'] = 'Empty Value'
            except WindowsError:  # pylint: disable=E0602
                value['vdata'] = ('(value not set)')
                value['vtype'] = 'REG_SZ'
            values.append(value)
    except WindowsError as exc:  # pylint: disable=E0602
        log.debug(exc)
        log.debug(r'Cannot find key: {0}\{1}'.format(hive, key))
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
    if PY2:
        ret = {'hive':  _mbcs_to_unicode(hive),
               'key':   _mbcs_to_unicode(key),
               'vname': _mbcs_to_unicode(vname),
               'vdata': None,
               'success': True}
        local_hive = _mbcs_to_unicode(hive)
        local_key = _unicode_to_mbcs(key)
        local_vname = _unicode_to_mbcs(vname)

    else:
        ret = {'hive': hive,
               'key':  key,
               'vname': vname,
               'vdata': None,
               'success': True}
        local_hive = hive
        local_key = key
        local_vname = vname

    if not vname:
        ret['vname'] = '(Default)'

    registry = Registry()
    hkey = registry.hkeys[local_hive]
    access_mask = registry.registry_32[use_32bit_registry]

    try:
        handle = _winreg.OpenKey(hkey, local_key, 0, access_mask)
        try:
            # QueryValueEx returns unicode data
            vdata, vtype = _winreg.QueryValueEx(handle, local_vname)
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
        log.debug('Cannot find key: {0}\\{1}'.format(local_hive, local_key))
        ret['comment'] = 'Cannot find key: {0}\\{1}'.format(local_hive, local_key)
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

    :param str key: The key (looks like a path) to the value name.

    :param str vname: The value name. These are the individual name/data pairs
        under the key. If not passed, the key (Default) value will be set.

    :param object vdata: The value data to be set.
        What the type of this paramater
        should be is determined by the value of the vtype
        paramater. The correspondence
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
        The possible values of the vtype paramater are indicated
        above in the description of the vdata paramater.

    :param bool use_32bit_registry: Sets the 32bit portion of the registry on
       64bit installations. On 32bit machines this is ignored.

    :param bool volatile: When this paramater has a value of True, the registry key will be
       made volatile (i.e. it will not persist beyond a system reset or shutdown).
       This paramater only has an effect when a key is being created and at no
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

    if PY2:
        try:
            local_hive = _mbcs_to_unicode(hive)
            local_key = _mbcs_to_unicode(key)
            local_vname = _mbcs_to_unicode(vname)
            local_vtype = _mbcs_to_unicode(vtype)
            local_vdata = _mbcs_to_unicode_wrap(vdata, local_vtype)
        except TypeError as exc:  # pylint: disable=E0602
            log.error(exc, exc_info=True)
            return False
    else:
        local_hive = hive
        local_key = key
        local_vname = vname
        local_vdata = vdata
        local_vtype = vtype

    registry = Registry()
    hkey = registry.hkeys[local_hive]
    vtype_value = registry.vtype[local_vtype]
    access_mask = registry.registry_32[use_32bit_registry] | _winreg.KEY_ALL_ACCESS
    if volatile:
        create_options = registry.opttype['REG_OPTION_VOLATILE']
    else:
        create_options = registry.opttype['REG_OPTION_NON_VOLATILE']

    try:
        handle, _ = RegCreateKeyEx(hkey, local_key, access_mask,
                                   Options=create_options)
        RegSetValueEx(handle, local_vname, 0, vtype_value, local_vdata)
        RegFlushKey(handle)
        RegCloseKey(handle)
        broadcast_change()
        return True
    except (win32apiError, SystemError, ValueError, TypeError) as exc:  # pylint: disable=E0602
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

    if PY2:
        local_hive = _mbcs_to_unicode(hive)
        local_key = _unicode_to_mbcs(key)
    else:
        local_hive = hive
        local_key = key

    # Instantiate the registry object
    registry = Registry()
    hkey = registry.hkeys[local_hive]
    key_path = local_key
    access_mask = registry.registry_32[use_32bit_registry] | _winreg.KEY_ALL_ACCESS

    if not _key_exists(local_hive, local_key, use_32bit_registry):
        return False

    if (len(key) > 1) and (key.count('\\', 1) < registry.subkey_slash_check[hkey]):
        log.error('Hive:{0} Key:{1}; key is too close to root, not safe to remove'.format(hive, key))
        return False

    # Functions for traversing the registry tree
    def _subkeys(_key):
        '''
        Enumerate keys
        '''
        i = 0
        while True:
            try:
                subkey = _winreg.EnumKey(_key, i)
                yield subkey
                i += 1
            except WindowsError:  # pylint: disable=E0602
                break

    def _traverse_registry_tree(_hkey, _keypath, _ret, _access_mask):
        '''
        Traverse the registry tree i.e. dive into the tree
        '''
        _key = _winreg.OpenKey(_hkey, _keypath, 0, _access_mask)
        for subkeyname in _subkeys(_key):
            subkeypath = r'{0}\{1}'.format(_keypath, subkeyname)
            _ret = _traverse_registry_tree(_hkey, subkeypath, _ret, access_mask)
            _ret.append('{0}'.format(subkeypath))
        return _ret

    # Get a reverse list of registry keys to be deleted
    key_list = []
    key_list = _traverse_registry_tree(hkey, key_path, key_list, access_mask)
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

    if PY2:
        local_hive = _mbcs_to_unicode(hive)
        local_key = _unicode_to_mbcs(key)
        local_vname = _unicode_to_mbcs(vname)
    else:
        local_hive = hive
        local_key = key
        local_vname = vname

    registry = Registry()
    hkey = registry.hkeys[local_hive]
    access_mask = registry.registry_32[use_32bit_registry] | _winreg.KEY_ALL_ACCESS

    try:
        handle = _winreg.OpenKey(hkey, local_key, 0, access_mask)
        _winreg.DeleteValue(handle, local_vname)
        _winreg.CloseKey(handle)
        broadcast_change()
        return True
    except WindowsError as exc:  # pylint: disable=E0602
        log.error(exc, exc_info=True)
        log.error('Hive: {0}'.format(local_hive))
        log.error('Key: {0}'.format(local_key))
        log.error('ValueName: {0}'.format(local_vname))
        log.error('32bit Reg: {0}'.format(use_32bit_registry))
        return False
