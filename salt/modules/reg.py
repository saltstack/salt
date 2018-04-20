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
``(Default)`` value corresponds to the Key, the rest are their own value pairs.

:depends:   - PyWin32
'''
# When production windows installer is using Python 3, Python 2 code can be removed
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging

# Import Salt libs
import salt.utils.platform
from salt.exceptions import CommandExecutionError

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

    if 'reg.read_value' not in __utils__:
        return (False, 'reg execution module failed to load: '
                       'The reg salt util is unavailable')

    return __virtualname__


def key_exists(hive, key, use_32bit_registry=False):
    '''
    Check that the key is found in the registry. This refers to keys and not
    value/data pairs.

    Args:

        hive (str): The hive to connect to

        key (str): The key to check

        use_32bit_registry (bool): Look in the 32bit portion of the registry

    Returns:
        bool: True if exists, otherwise False

    CLI Example:

        .. code-block:: bash

            salt '*' reg.key_exists HKLM SOFTWARE\Microsoft
    '''
    return __utils__['reg.key_exists'](hive=hive,
                                       key=key,
                                       use_32bit_registry=use_32bit_registry)


def broadcast_change():
    '''
    Refresh the windows environment.

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

        .. code-block:: bash

            salt '*' reg.broadcast_change
    '''
    return salt.utils.win_functions.broadcast_setting_change('Environment')


def list_keys(hive, key=None, use_32bit_registry=False):
    '''
    Enumerates the subkeys in a registry key or hive.

    Args:

        hive (str):
            The name of the hive. Can be one of the following:

                - HKEY_LOCAL_MACHINE or HKLM
                - HKEY_CURRENT_USER or HKCU
                - HKEY_USER or HKU
                - HKEY_CLASSES_ROOT or HKCR
                - HKEY_CURRENT_CONFIG or HKCC

        key (str):
            The key (looks like a path) to the value name. If a key is not
            passed, the keys under the hive will be returned.

        use_32bit_registry (bool):
            Accesses the 32bit portion of the registry on 64 bit installations.
            On 32bit machines this is ignored.

    Returns:
        list: A list of keys/subkeys under the hive or key.

    CLI Example:

        .. code-block:: bash

            salt '*' reg.list_keys HKLM 'SOFTWARE'
    '''
    return __utils__['reg.list_keys'](hive=hive,
                                      key=key,
                                      use_32bit_registry=use_32bit_registry)


def list_values(hive, key=None, use_32bit_registry=False, include_default=True):
    '''
    Enumerates the values in a registry key or hive.

    Args:

        hive (str):
            The name of the hive. Can be one of the following:

                - HKEY_LOCAL_MACHINE or HKLM
                - HKEY_CURRENT_USER or HKCU
                - HKEY_USER or HKU
                - HKEY_CLASSES_ROOT or HKCR
                - HKEY_CURRENT_CONFIG or HKCC

        key (str):
            The key (looks like a path) to the value name. If a key is not
            passed, the values under the hive will be returned.

        use_32bit_registry (bool):
            Accesses the 32bit portion of the registry on 64 bit installations.
            On 32bit machines this is ignored.

        include_default (bool):
            Toggle whether to include the '(Default)' value.

    Returns:
        list: A list of values under the hive or key.

    CLI Example:

        .. code-block:: bash

            salt '*' reg.list_values HKLM 'SYSTEM\\CurrentControlSet\\Services\\Tcpip'
    '''
    return __utils__['reg.list_values'](hive=hive,
                                        key=key,
                                        use_32bit_registry=use_32bit_registry,
                                        include_default=include_default)


def read_value(hive, key, vname=None, use_32bit_registry=False):
    r'''
    Reads a registry value entry or the default value for a key.

    Args:

        hive (str): The name of the hive. Can be one of the following:

            - HKEY_LOCAL_MACHINE or HKLM
            - HKEY_CURRENT_USER or HKCU
            - HKEY_USER or HKU
            - HKEY_CLASSES_ROOT or HKCR
            - HKEY_CURRENT_CONFIG or HKCC

        key (str):
            The key (looks like a path) to the value name.

        vname (str):
            The value name. These are the individual name/data pairs under the
            key. If not passed, the key (Default) value will be returned.

        use_32bit_registry (bool):
            Accesses the 32bit portion of the registry on 64bit installations.
            On 32bit machines this is ignored.

    Returns:
        dict: A dictionary containing the passed settings as well as the
        value_data if successful. If unsuccessful, sets success to False.

        If vname is not passed:

            - Returns the first unnamed value (Default) as a string.
            - Returns none if first unnamed value is empty.
            - Returns False if key not found.

    CLI Example:

        .. code-block:: bash

            salt '*' reg.read_value HKEY_LOCAL_MACHINE 'SOFTWARE\Salt' 'version'
    '''
    return __utils__['reg.read_value'](hive=hive,
                                       key=key,
                                       vname=vname,
                                       use_32bit_registry=use_32bit_registry)


def set_value(hive,
              key,
              vname=None,
              vdata=None,
              vtype='REG_SZ',
              use_32bit_registry=False,
              volatile=False):
    '''
    Sets a registry value entry or the default value for a key.

    Args:

        hive (str):
            The name of the hive. Can be one of the following

                - HKEY_LOCAL_MACHINE or HKLM
                - HKEY_CURRENT_USER or HKCU
                - HKEY_USER or HKU
                - HKEY_CLASSES_ROOT or HKCR
                - HKEY_CURRENT_CONFIG or HKCC

        key (str):
            The key (looks like a path) to the value name.

        vname (str):
            The value name. These are the individual name/data pairs under the
            key. If not passed, the key (Default) value will be set.

        vdata (str, int, list):
            The value you'd like to set. If a value name (vname) is passed, this
            will be the data for that value name. If not, this will be the
            (Default) value for the key.

            The type of data this parameter expects is determined by the value
            type specified in ``vtype``. The correspondence is as follows:

                - REG_BINARY: Binary data (str in Py2, bytes in Py3)
                - REG_DWORD: int
                - REG_EXPAND_SZ: str
                - REG_MULTI_SZ: list of str
                - REG_QWORD: int
                - REG_SZ: str

                .. note::
                    When setting REG_BINARY, string data will be converted to
                    binary.

            .. note::
                The type for the (Default) value is always REG_SZ and cannot be
                changed.

            .. note::
                This parameter is optional. If ``vdata`` is not passed, the Key
                will be created with no associated item/value pairs.

        vtype (str):
            The value type. The possible values of the vtype parameter are
            indicated above in the description of the vdata parameter.

        use_32bit_registry (bool):
            Sets the 32bit portion of the registry on 64bit installations. On
            32bit machines this is ignored.

        volatile (bool):
            When this parameter has a value of True, the registry key will be
            made volatile (i.e. it will not persist beyond a system reset or
            shutdown). This parameter only has an effect when a key is being
            created and at no other time.

    Returns:
        bool: True if successful, otherwise False

    CLI Example:

        .. code-block:: bash

            salt '*' reg.set_value HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'version' '2015.5.2'

    CLI Example:

        This function is strict about the type of vdata. For instance this
        example will fail because vtype has a value of REG_SZ and vdata has a
        type of int (as opposed to str as expected).

        .. code-block:: bash

            salt '*' reg.set_value HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'str_data' 1.2

    CLI Example:

        In this next example vdata is properly quoted and should succeed.

        .. code-block:: bash

            salt '*' reg.set_value HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'str_data' vtype=REG_SZ vdata="'1.2'"

    CLI Example:

        This is an example of using vtype REG_BINARY.

        .. code-block:: bash

            salt '*' reg.set_value HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'bin_data' vtype=REG_BINARY vdata='Salty Data'

    CLI Example:

        An example of using vtype REG_MULTI_SZ is as follows:

        .. code-block:: bash

            salt '*' reg.set_value HKEY_LOCAL_MACHINE 'SOFTWARE\\Salt' 'list_data' vtype=REG_MULTI_SZ vdata='["a", "b", "c"]'
    '''
    return __utils__['reg.set_value'](hive=hive,
                                      key=key,
                                      vname=vname,
                                      vdata=vdata,
                                      vtype=vtype,
                                      use_32bit_registry=use_32bit_registry,
                                      volatile=volatile)


def delete_key_recursive(hive, key, use_32bit_registry=False):
    '''
    .. versionadded:: 2015.5.4

    Delete a registry key to include all subkeys.

    Args:

        hive (str):
            The name of the hive. Can be one of the following

                - HKEY_LOCAL_MACHINE or HKLM
                - HKEY_CURRENT_USER or HKCU
                - HKEY_USER or HKU
                - HKEY_CLASSES_ROOT or HKCR
                - HKEY_CURRENT_CONFIG or HKCC

            key (str):
                The key to remove (looks like a path)

            use_32bit_registry (bool):
                Deletes the 32bit portion of the registry on 64bit
                installations. On 32bit machines this is ignored.

    Returns:
        dict: A dictionary listing the keys that deleted successfully as well as
            those that failed to delete.

    CLI Example:

        The following example will remove ``salt`` and all its subkeys from the
        ``SOFTWARE`` key in ``HKEY_LOCAL_MACHINE``:

        .. code-block:: bash

            salt '*' reg.delete_key_recursive HKLM SOFTWARE\\salt
    '''
    return __utils__['reg.delete_key_recursive'](hive=hive,
                                                 key=key,
                                                 use_32bit_registry=use_32bit_registry)


def delete_value(hive, key, vname=None, use_32bit_registry=False):
    '''
    Delete a registry value entry or the default value for a key.

    Args:

        hive (str):
            The name of the hive. Can be one of the following

                - HKEY_LOCAL_MACHINE or HKLM
                - HKEY_CURRENT_USER or HKCU
                - HKEY_USER or HKU
                - HKEY_CLASSES_ROOT or HKCR
                - HKEY_CURRENT_CONFIG or HKCC

        key (str):
            The key (looks like a path) to the value name.

        vname (str):
            The value name. These are the individual name/data pairs under the
            key. If not passed, the key (Default) value will be deleted.

        use_32bit_registry (bool):
            Deletes the 32bit portion of the registry on 64bit installations. On
            32bit machines this is ignored.

    Return:
        bool: True if successful, otherwise False

    CLI Example:

        .. code-block:: bash

            salt '*' reg.delete_value HKEY_CURRENT_USER 'SOFTWARE\\Salt' 'version'
    '''
    return __utils__['reg.delete_value'](hive=hive,
                                         key=key,
                                         vname=vname,
                                         use_32bit_registry=use_32bit_registry)


def import_file(source, use_32bit_registry=False):
    '''
    Import registry settings from a Windows ``REG`` file by invoking ``REG.EXE``.

    .. versionadded:: 2018.3.0

    Args:

        source (str):
            The full path of the ``REG`` file. This can be either a local file
            path or a URL type supported by salt (e.g. ``salt://salt_master_path``)

        use_32bit_registry (bool):
            If the value of this parameter is ``True`` then the ``REG`` file
            will be imported into the Windows 32 bit registry. Otherwise the
            Windows 64 bit registry will be used.

    Returns:
        bool: True if successful, otherwise an error is raised

    Raises:
        ValueError: If the value of ``source`` is an invalid path or otherwise
            causes ``cp.cache_file`` to return ``False``
        CommandExecutionError: If ``reg.exe`` exits with a non-0 exit code

    CLI Example:

        .. code-block:: bash

            salt machine1 reg.import_file salt://win/printer_config/110_Canon/postinstall_config.reg

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
