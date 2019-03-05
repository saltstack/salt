# -*- coding: utf-8 -*-
r'''
Manage the Windows registry
===========================

Many python developers think of registry keys as if they were python keys in a
dictionary which is not the case. The windows registry is broken down into the
following components:

Hives
-----

This is the top level of the registry. They all begin with HKEY.

    - HKEY_CLASSES_ROOT (HKCR)
    - HKEY_CURRENT_USER(HKCU)
    - HKEY_LOCAL MACHINE (HKLM)
    - HKEY_USER (HKU)
    - HKEY_CURRENT_CONFIG

Keys
----

Hives contain keys. These are basically the folders beneath the hives. They can
contain any number of subkeys.

When passing the hive\key values they must be quoted correctly depending on the
backslashes being used (``\`` vs ``\\``). The way backslashes are handled in
the state file is different from the way they are handled when working on the
CLI. The following are valid methods of passing the hive\key:

Using single backslashes:
    HKLM\SOFTWARE\Python
    'HKLM\SOFTWARE\Python'

Using double backslashes:
    "HKLM\\SOFTWARE\\Python"

Values or Entries
-----------------

Values or Entries are the name/data pairs beneath the keys and subkeys. All keys
have a default name/data pair. The name is ``(Default)`` with a displayed value
of ``(value not set)``. The actual value is Null.

Example
-------

The following example is taken from the windows startup portion of the registry:

.. code-block:: text

    [HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Run]
    "RTHDVCPL"="\"C:\\Program Files\\Realtek\\Audio\\HDA\\RtkNGUI64.exe\" -s"
    "NvBackend"="\"C:\\Program Files (x86)\\NVIDIA Corporation\\Update Core\\NvBackend.exe\""
    "BTMTrayAgent"="rundll32.exe \"C:\\Program Files (x86)\\Intel\\Bluetooth\\btmshellex.dll\",TrayApp"

In this example these are the values for each:

Hive:
    ``HKEY_LOCAL_MACHINE``

Key and subkeys:
    ``SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run``

Value:

- There are 3 value names: ``RTHDVCPL``, ``NvBackend``, and ``BTMTrayAgent``
- Each value name has a corresponding value

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import salt.utils.stringutils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Load this state if the reg module exists
    '''
    if 'reg.read_value' not in __utils__:
        return (False, 'reg state module failed to load: '
                       'missing util function: reg.read_value')

    if 'reg.set_value' not in __utils__:
        return (False, 'reg state module failed to load: '
                       'missing util function: reg.set_value')

    if 'reg.delete_value' not in __utils__:
        return (False, 'reg state module failed to load: '
                       'missing util function: reg.delete_value')

    if 'reg.delete_key_recursive' not in __utils__:
        return (False, 'reg state module failed to load: '
                       'missing util function: reg.delete_key_recursive')

    return 'reg'


def _parse_key(key):
    '''
    split the hive from the key
    '''
    splt = key.split("\\")
    hive = splt.pop(0)
    key = '\\'.join(splt)
    return hive, key


def present(name,
            vname=None,
            vdata=None,
            vtype='REG_SZ',
            use_32bit_registry=False):
    r'''
    Ensure a registry key or value is present.

    Args:

        name (str):
            A string value representing the full path of the key to include the
            HIVE, Key, and all Subkeys. For example:

            ``HKEY_LOCAL_MACHINE\\SOFTWARE\\Salt``

            Valid hive values include:

                - HKEY_CURRENT_USER or HKCU
                - HKEY_LOCAL_MACHINE or HKLM
                - HKEY_USERS or HKU

        vname (str):
            The name of the value you'd like to create beneath the Key. If this
            parameter is not passed it will assume you want to set the
            ``(Default)`` value

        vdata (str, int, list, bytes):
            The value you'd like to set. If a value name (``vname``) is passed,
            this will be the data for that value name. If not, this will be the
            ``(Default)`` value for the key.

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
                    binary automatically. To pass binary data, use the built-in
                    yaml tag ``!!binary`` to denote the actual binary
                    characters. For example, the following lines will both set
                    the same data in the registry:

                    - ``vdata: Salty Test``
                    - ``vdata: !!binary U2FsdHkgVGVzdA==\n``

                    For more information about the ``!!binary`` tag see
                    `here <http://yaml.org/type/binary.html>`_

            .. note::
                The type for the ``(Default)`` value is always REG_SZ and cannot
                be changed. This parameter is optional. If not passed, the Key
                will be created with no associated item/value pairs.

        vtype (str):
            The value type for the data you wish to store in the registry. Valid
            values are:

                - REG_BINARY
                - REG_DWORD
                - REG_EXPAND_SZ
                - REG_MULTI_SZ
                - REG_QWORD
                - REG_SZ (Default)

        use_32bit_registry (bool):
            Use the 32bit portion of the registry. Applies only to 64bit
            windows. 32bit Windows will ignore this parameter. Default is False.

    Returns:
        dict: A dictionary showing the results of the registry operation.

    Example:

        The following example will set the ``(Default)`` value for the
        ``SOFTWARE\\Salt`` key in the ``HKEY_CURRENT_USER`` hive to
        ``2016.3.1``:

        .. code-block:: yaml

            HKEY_CURRENT_USER\\SOFTWARE\\Salt:
              reg.present:
                - vdata: 2016.3.1

    Example:

        The following example will set the value for the ``version`` entry under
        the ``SOFTWARE\\Salt`` key in the ``HKEY_CURRENT_USER`` hive to
        ``2016.3.1``. The value will be reflected in ``Wow6432Node``:

        .. code-block:: yaml

            HKEY_CURRENT_USER\\SOFTWARE\\Salt:
              reg.present:
                - vname: version
                - vdata: 2016.3.1

        In the above example the path is interpreted as follows:

            - ``HKEY_CURRENT_USER`` is the hive
            - ``SOFTWARE\\Salt`` is the key
            - ``vname`` is the value name ('version') that will be created under the key
            - ``vdata`` is the data that will be assigned to 'version'

    Example:

        Binary data can be set in two ways. The following two examples will set
        a binary value of ``Salty Test``

        .. code-block:: yaml

            no_conversion:
              reg.present:
                - name: HKLM\SOFTWARE\SaltTesting
                - vname: test_reg_binary_state
                - vdata: Salty Test
                - vtype: REG_BINARY

            conversion:
              reg.present:
                - name: HKLM\SOFTWARE\SaltTesting
                - vname: test_reg_binary_state_with_tag
                - vdata: !!binary U2FsdHkgVGVzdA==\n
                - vtype: REG_BINARY

    Example:

        To set a ``REG_MULTI_SZ`` value:

        .. code-block:: yaml

            reg_multi_sz:
              reg.present:
                - name: HKLM\SOFTWARE\Salt
                - vname: reg_multi_sz
                - vdata:
                  - list item 1
                  - list item 2
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    hive, key = _parse_key(name)

    # Determine what to do
    reg_current = __utils__['reg.read_value'](hive=hive,
                                              key=key,
                                              vname=vname,
                                              use_32bit_registry=use_32bit_registry)

    if vdata == reg_current['vdata'] and reg_current['success']:
        ret['comment'] = '{0} in {1} is already configured' \
                         ''.format(salt.utils.stringutils.to_unicode(vname, 'utf-8') if vname else '(Default)',
                                   salt.utils.stringutils.to_unicode(name, 'utf-8'))
        return ret

    vdata_decoded = __utils__['reg.cast_vdata'](vdata=vdata, vtype=vtype)

    add_change = {'Key': r'{0}\{1}'.format(hive, key),
                  'Entry': '{0}'.format(salt.utils.stringutils.to_unicode(vname, 'utf-8') if vname else '(Default)'),
                  'Value': vdata_decoded}

    # Check for test option
    if __opts__['test']:
        ret['result'] = None
        ret['changes'] = {'reg': {'Will add': add_change}}
        return ret

    # Configure the value
    ret['result'] = __utils__['reg.set_value'](hive=hive,
                                               key=key,
                                               vname=vname,
                                               vdata=vdata,
                                               vtype=vtype,
                                               use_32bit_registry=use_32bit_registry)

    if not ret['result']:
        ret['changes'] = {}
        ret['comment'] = r'Failed to add {0} to {1}\{2}'.format(name, hive, key)
    else:
        ret['changes'] = {'reg': {'Added': add_change}}
        ret['comment'] = r'Added {0} to {1}\{2}'.format(name, hive, key)

    return ret


def absent(name, vname=None, use_32bit_registry=False):
    r'''
    Ensure a registry value is removed. To remove a key use key_absent.

    Args:
        name (str):
            A string value representing the full path of the key to include the
            HIVE, Key, and all Subkeys. For example:

            ``HKEY_LOCAL_MACHINE\\SOFTWARE\\Salt``

            Valid hive values include:

                - HKEY_CURRENT_USER or HKCU
                - HKEY_LOCAL_MACHINE or HKLM
                - HKEY_USERS or HKU

        vname (str):
            The name of the value you'd like to create beneath the Key. If this
            parameter is not passed it will assume you want to set the
            ``(Default)`` value

        use_32bit_registry (bool):
            Use the 32bit portion of the registry. Applies only to 64bit
            windows. 32bit Windows will ignore this parameter. Default is False.

    Returns:
        dict: A dictionary showing the results of the registry operation.

    CLI Example:

        .. code-block:: yaml

            'HKEY_CURRENT_USER\\SOFTWARE\\Salt':
              reg.absent
                - vname: version

        In the above example the value named ``version`` will be removed from
        the SOFTWARE\\Salt key in the HKEY_CURRENT_USER hive. If ``vname`` was
        not passed, the ``(Default)`` value would be deleted.
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    hive, key = _parse_key(name)

    # Determine what to do
    reg_check = __utils__['reg.read_value'](hive=hive,
                                            key=key,
                                            vname=vname,
                                            use_32bit_registry=use_32bit_registry)
    if not reg_check['success'] or reg_check['vdata'] == '(value not set)':
        ret['comment'] = '{0} is already absent'.format(name)
        return ret

    remove_change = {'Key': r'{0}\{1}'.format(hive, key),
                     'Entry': '{0}'.format(vname if vname else '(Default)')}

    # Check for test option
    if __opts__['test']:
        ret['result'] = None
        ret['changes'] = {'reg': {'Will remove': remove_change}}
        return ret

    # Delete the value
    ret['result'] = __utils__['reg.delete_value'](hive=hive,
                                                  key=key,
                                                  vname=vname,
                                                  use_32bit_registry=use_32bit_registry)
    if not ret['result']:
        ret['changes'] = {}
        ret['comment'] = r'Failed to remove {0} from {1}'.format(key, hive)
    else:
        ret['changes'] = {'reg': {'Removed': remove_change}}
        ret['comment'] = r'Removed {0} from {1}'.format(key, hive)

    return ret


def key_absent(name, use_32bit_registry=False):
    r'''
    .. versionadded:: 2015.5.4

    Ensure a registry key is removed. This will remove the key, subkeys, and all
    value entries.

    Args:

        name (str):
            A string representing the full path to the key to be removed to
            include the hive and the keypath. The hive can be any of the
            following:

                - HKEY_LOCAL_MACHINE or HKLM
                - HKEY_CURRENT_USER or HKCU
                - HKEY_USER or HKU

        use_32bit_registry (bool):
            Use the 32bit portion of the registry. Applies only to 64bit
            windows. 32bit Windows will ignore this parameter. Default is False.

    Returns:
        dict: A dictionary showing the results of the registry operation.


    CLI Example:

        The following example will delete the ``SOFTWARE\DeleteMe`` key in the
        ``HKEY_LOCAL_MACHINE`` hive including all its subkeys and value pairs.

        .. code-block:: yaml

            remove_key_demo:
              reg.key_absent:
                - name: HKEY_CURRENT_USER\SOFTWARE\DeleteMe

        In the above example the path is interpreted as follows:

            - ``HKEY_CURRENT_USER`` is the hive
            - ``SOFTWARE\DeleteMe`` is the key
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    hive, key = _parse_key(name)

    # Determine what to do
    if not __utils__['reg.read_value'](hive=hive,
                                       key=key,
                                       use_32bit_registry=use_32bit_registry)['success']:
        ret['comment'] = '{0} is already absent'.format(name)
        return ret

    ret['changes'] = {
        'reg': {
            'Removed': {
                'Key': r'{0}\{1}'.format(hive, key)}}}

    # Check for test option
    if __opts__['test']:
        ret['result'] = None
        return ret

    # Delete the value
    __utils__['reg.delete_key_recursive'](hive=hive,
                                          key=key,
                                          use_32bit_registry=use_32bit_registry)
    if __utils__['reg.read_value'](hive=hive,
                                   key=key,
                                   use_32bit_registry=use_32bit_registry)['success']:
        ret['result'] = False
        ret['changes'] = {}
        ret['comment'] = 'Failed to remove registry key {0}'.format(name)

    return ret
