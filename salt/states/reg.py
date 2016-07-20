# -*- coding: utf-8 -*-
r'''
===========================
Manage the Windows registry
===========================
Many python developers think of registry keys as if they were python keys in a
dictionary which is not the case. The windows registry is broken down into the
following components:

-----
Hives
-----

This is the top level of the registry. They all begin with HKEY.
- HKEY_CLASSES_ROOT (HKCR)
- HKEY_CURRENT_USER(HKCU)
- HKEY_LOCAL MACHINE (HKLM)
- HKEY_USER (HKU)
- HKEY_CURRENT_CONFIG

----
Keys
----

Hives contain keys. These are basically the folders beneath the hives. They can
contain any number of subkeys.

-----------------
Values or Entries
-----------------

Values or Entries are the name/data pairs beneath the keys and subkeys. All keys
have a default name/data pair. It is usually "(Default)"="(value not set)". The
actual value for the name and the date is Null. The registry editor will display
"(Default)" and "(value not set)".

-------
Example
-------

The following example is taken from the windows startup portion of the registry:
```
[HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Run]
"RTHDVCPL"="\"C:\\Program Files\\Realtek\\Audio\\HDA\\RtkNGUI64.exe\" -s"
"NvBackend"="\"C:\\Program Files (x86)\\NVIDIA Corporation\\Update Core\\NvBackend.exe\""
"BTMTrayAgent"="rundll32.exe \"C:\\Program Files (x86)\\Intel\\Bluetooth\\btmshellex.dll\",TrayApp"
```
In this example these are the values for each:

Hive: `HKEY_LOCAL_MACHINE`

Key and subkeys: `SOFTWARE\Microsoft\Windows\CurrentVersion\Run`

Value:
    - There are 3 value names: `RTHDVCPL`, `NvBackend`, and `BTMTrayAgent`
    - Each value name has a corresponding value
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Load this state if the reg module exists
    '''
    return 'reg' if 'reg.read_key' in __salt__ else False


def _parse_key_value(key):
    '''
    split the full path in the registry to the key and the rest
    '''
    splt = key.split("\\")
    hive = splt.pop(0)
    vname = splt.pop(-1)
    key = '\\'.join(splt)
    return hive, key, vname


def _parse_key(key):
    '''
    split the hive from the key
    '''
    splt = key.split("\\")
    hive = splt.pop(0)
    key = '\\'.join(splt)
    return hive, key


def present(name,
            value=None,
            vname=None,
            vdata=None,
            vtype='REG_SZ',
            reflection=True,
            use_32bit_registry=False):
    '''
    Ensure a registry key or value is present.

    :param str name: A string value representing the full path of the key to
    include the HIVE, Key, and all Subkeys. For example:

    ``HKEY_LOCAL_MACHINE\\SOFTWARE\\Salt``

    Valid hive values include:
    - HKEY_CURRENT_USER or HKCU
    - HKEY_LOCAL_MACHINE or HKLM
    - HKEY_USERS or HKU

    :param str value: Deprecated. Use vname and vdata instead. Included here for
    backwards compatibility.

    :param str vname: The name of the value you'd like to create beneath the
    Key. If this parameter is not passed it will assume you want to set the
    (Default) value

    :param str vdata: The value you'd like to set for the Key. If a value name
    (vname) is passed, this will be the data for that value name. If not, this
    will be the (Default) value for the key.

    The type for the (Default) value is always REG_SZ and cannot be changed.
    This parameter is optional. If not passed, the Key will be created with no
    associated item/value pairs.

    :param str vtype: The value type for the data you wish to store in the
    registry. Valid values are:

    - REG_BINARY
    - REG_DWORD
    - REG_EXPAND_SZ
    - REG_MULTI_SZ
    - REG_SZ (Default)

    :param bool reflection: On 64 bit machines a duplicate value will be created
    in the ``Wow6432Node`` for 32bit programs. This only applies to the SOFTWARE
    key. This option is ignored on 32bit operating systems. This value defaults
    to True. Set it to False to disable reflection.

    .. deprecated:: 2015.8.2
       Use `use_32bit_registry` instead.
       The parameter seems to have no effect since Windows 7 / Windows 2008R2
       removed support for reflection. The parameter will be removed in Boron.

    :param bool use_32bit_registry: Use the 32bit portion of the registry.
    Applies only to 64bit windows. 32bit Windows will ignore this parameter.
    Default if False.

    :return: Returns a dictionary showing the results of the registry operation.
    :rtype: dict

    The following example will set the ``(Default)`` value for the
    ``SOFTWARE\\Salt`` key in the ``HKEY_CURRENT_USER`` hive to ``0.15.3``. The
    value will not be reflected in ``Wow6432Node``:

    Example:

    .. code-block:: yaml

        HKEY_CURRENT_USER\\SOFTWARE\\Salt:
          reg.present:
            - vdata: 0.15.3
            - reflection: False

    The following example will set the value for the ``version`` entry under the
    ``SOFTWARE\\Salt`` key in the ``HKEY_CURRENT_USER`` hive to ``0.15.3``. The
    value will be reflected in ``Wow6432Node``:

    Example:

    .. code-block:: yaml

        HKEY_CURRENT_USER\\SOFTWARE\\Salt:
          reg.present:
            - vname: version
            - vdata: 0.15.3

    In the above example the path is interpreted as follows:
    - ``HKEY_CURRENT_USER`` is the hive
    - ``SOFTWARE\\Salt`` is the key
    - ``vname`` is the value name ('version') that will be created under the key
    - ``vdata`` is the data that will be assigned to 'version'
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    # This is for backwards compatibility
    # If 'value' is passed a value, vdata becomes value and the vname is
    # obtained from the key path
    if value or value in [0, '']:
        hive, key, vname = _parse_key_value(name)
        vdata = value
        ret['comment'] = 'State file is using deprecated syntax. Please update.'
        salt.utils.warn_until(
            'Boron',
            'The \'value\' argument has been deprecated. '
            'Please use vdata instead.'
        )
    else:
        hive, key = _parse_key(name)

    # Determine what to do
    reg_current = __salt__['reg.read_value'](hive=hive,
                                             key=key,
                                             vname=vname,
                                             use_32bit_registry=use_32bit_registry)

    if vdata == reg_current['vdata'] and reg_current['success']:
        ret['comment'] = '{0} in {1} is already configured'.\
            format(vname if vname else '(Default)', name)
        return ret

    add_change = {'Key': r'{0}\{1}'.format(hive, key),
                  'Entry': '{0}'.format(vname if vname else '(Default)'),
                  'Value': '{0}'.format(vdata)}

    # Check for test option
    if __opts__['test']:
        ret['result'] = None
        ret['changes'] = {'reg': {'Will add': add_change}}
        return ret

    # Configure the value
    ret['result'] = __salt__['reg.set_value'](hive=hive,
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
    '''
    Ensure a registry value is removed. To remove a key use key_absent.

    :param str name: A string value representing the full path of the key to
    include the HIVE, Key, and all Subkeys. For example:

    ``HKEY_LOCAL_MACHINE\\SOFTWARE\\Salt``

    Valid hive values include:

    - HKEY_CURRENT_USER or HKCU
    - HKEY_LOCAL_MACHINE or HKLM
    - HKEY_USERS or HKU

    :param str vname: The name of the value you'd like to create beneath the
    Key. If this parameter is not passed it will assume you want to set the
    (Default) value

    :param bool use_32bit_registry: Use the 32bit portion of the registry.
    Applies only to 64bit windows. 32bit Windows will ignore this parameter.
    Default if False.

    :return: Returns a dictionary showing the results of the registry operation.
    :rtype: dict

    CLI Example:

    .. code-block:: yaml

        'HKEY_CURRENT_USER\\SOFTWARE\\Salt\\version':
          reg.absent

    In the above example the path is interpreted as follows:

    - ``HKEY_CURRENT_USER`` is the hive
    - ``SOFTWARE\\Salt`` is the key
    - ``version`` is the value name

    So the value ``version`` will be deleted from the ``SOFTWARE\\Salt`` key in
    the ``HKEY_CURRENT_USER`` hive.
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    hive, key = _parse_key(name)

    # Determine what to do
    reg_check = __salt__['reg.read_value'](hive=hive,
                                           key=key,
                                           vname=vname,
                                           use_32bit_registry=use_32bit_registry)
    if not reg_check['success'] or reg_check['vdata'] == '(value not set)':
        if not vname:
            hive, key, vname = _parse_key_value(name)
            reg_check = __salt__['reg.read_value'](hive=hive,
                                                   key=key,
                                                   vname=vname,
                                                   use_32bit_registry=use_32bit_registry)
            if not reg_check['success'] or reg_check['vdata'] == '(value not set)':
                ret['comment'] = '{0} is already absent'.format(name)
                return ret
        else:
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
    ret['result'] = __salt__['reg.delete_value'](hive=hive,
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


def key_absent(name, force=False, use_32bit_registry=False):
    r'''
    .. versionadded:: 2015.5.4

    Ensure a registry key is removed. This will remove a key and all value
    entries it contains. It will fail if the key contains subkeys.

    :param str name: A string representing the full path to the key to be
    removed to include the hive and the keypath. The hive can be any of the following:

    - HKEY_LOCAL_MACHINE or HKLM
    - HKEY_CURRENT_USER or HKCU
    - HKEY_USER or HKU

    :param bool force: A boolean value indicating that all subkeys should be
    deleted with the key. If force=False and subkeys exists beneath the key you
    want to delete, key_absent will fail. Use with caution. The default is False.

    :return: Returns a dictionary showing the results of the registry operation.
    :rtype: dict

    The following example will delete the ``SOFTWARE\Salt`` key and all subkeys
    under the ``HKEY_CURRENT_USER`` hive.

    Example:

    .. code-block:: yaml

        'HKEY_CURRENT_USER\SOFTWARE\Salt':
          reg.key_absent:
            - force: True

    In the above example the path is interpreted as follows:

    - ``HKEY_CURRENT_USER`` is the hive
    - ``SOFTWARE\Salt`` is the key
    '''
    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    hive, key = _parse_key(name)

    # Determine what to do
    if not __salt__['reg.read_value'](hive=hive,
                                      key=key,
                                      use_32bit_registry=use_32bit_registry)['success']:
        ret['comment'] = '{0} is already absent'.format(name)
        return ret

    ret['changes'] = {'reg': {
        'Removed': {
            'Key': r'{0}\{1}'.format(hive, key)
        }}}

    # Check for test option
    if __opts__['test']:
        ret['result'] = None
        return ret

    # Delete the value
    __salt__['reg.delete_key_recursive'](hive=hive,
                                         key=key,
                                         use_32bit_registry=use_32bit_registry)
    if __salt__['reg.read_value'](hive=hive,
                                  key=key,
                                  use_32bit_registry=use_32bit_registry)['success']:
        ret['result'] = False
        ret['changes'] = {}
        ret['comment'] = 'Failed to remove registry key {0}'.format(name)

    return ret
