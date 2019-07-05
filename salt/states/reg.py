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
import sys
import io
from salt.ext.six.moves import configparser
from salt.exceptions import CommandExecutionError

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
            use_32bit_registry=False,
            win_owner=None,
            win_perms=None,
            win_deny_perms=None,
            win_inheritance=True,
            win_perms_reset=False):
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

        win_owner (str):
            The owner of the registry key. If this is not passed, the account
            under which Salt is running will be used.

            .. note::
                Owner is set for the key that contains the value/data pair. You
                cannot set ownership on value/data pairs themselves.

            .. versionadded:: 2019.2.0

        win_perms (dict):
            A dictionary containing permissions to grant and their propagation.
            If not passed the 'Grant` permissions will not be modified.

            .. note::
                Permissions are set for the key that contains the value/data
                pair. You cannot set permissions on value/data pairs themselves.

            For each user specify the account name, with a sub dict for the
            permissions to grant and the 'Applies to' setting. For example:
            ``{'Administrators': {'perms': 'full_control', 'applies_to':
            'this_key_subkeys'}}``. ``perms`` must be specified.

            Registry permissions are specified using the ``perms`` key. You can
            specify a single basic permission or a list of advanced perms. The
            following are valid perms:

                Basic (passed as a string):
                    - full_control
                    - read
                    - write

                Advanced (passed as a list):
                    - delete
                    - query_value
                    - set_value
                    - create_subkey
                    - enum_subkeys
                    - notify
                    - create_link
                    - read_control
                    - write_dac
                    - write_owner

            The 'Applies to' setting is optional. It is specified using the
            ``applies_to`` key. If not specified ``this_key_subkeys`` is used.
            Valid options are:

                Applies to settings:
                    - this_key_only
                    - this_key_subkeys
                    - subkeys_only

            .. versionadded:: 2019.2.0

        win_deny_perms (dict):
            A dictionary containing permissions to deny and their propagation.
            If not passed the `Deny` permissions will not be modified.

            .. note::
                Permissions are set for the key that contains the value/data
                pair. You cannot set permissions on value/data pairs themselves.

            Valid options are the same as those specified in ``win_perms``

            .. note::
                'Deny' permissions always take precedence over 'grant'
                 permissions.

            .. versionadded:: 2019.2.0

        win_inheritance (bool):
            ``True`` to inherit permissions from the parent key. ``False`` to
            disable inheritance. Default is ``True``.

            .. note::
                Inheritance is set for the key that contains the value/data
                pair. You cannot set inheritance on value/data pairs themselves.

            .. versionadded:: 2019.2.0

        win_perms_reset (bool):
            If ``True`` the existing DACL will be cleared and replaced with the
            settings defined in this function. If ``False``, new entries will be
            appended to the existing DACL. Default is ``False``

            .. note::
                Perms are reset for the key that contains the value/data pair.
                You cannot set permissions on value/data pairs themselves.

            .. versionadded:: 2019.2.0

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

    Example:

    To ensure a key is present and has permissions:

    .. code-block:: yaml

        set_key_permissions:
          reg.present:
            - name: HKLM\SOFTWARE\Salt
            - vname: version
            - vdata: 2016.3.1
            - win_owner: Administrators
            - win_perms:
                jsnuffy:
                  perms: full_control
                sjones:
                  perms:
                    - read_control
                    - enum_subkeys
                    - query_value
                  applies_to:
                    - this_key_only
            - win_deny_perms:
                bsimpson:
                  perms: full_control
                  applies_to: this_key_subkeys
            - win_inheritance: True
            - win_perms_reset: True
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

    # Check if the key already exists
    # If so, check perms
    # We check `vdata` and `success` because `vdata` can be None
    if vdata == reg_current['vdata'] and reg_current['success']:
        ret['comment'] = '{0} in {1} is already present' \
                         ''.format(salt.utils.stringutils.to_unicode(vname, 'utf-8') if vname else '(Default)',
                                   salt.utils.stringutils.to_unicode(name, 'utf-8'))
        return __utils__['dacl.check_perms'](
            obj_name='\\'.join([hive, key]),
            obj_type='registry32' if use_32bit_registry else 'registry',
            ret=ret,
            owner=win_owner,
            grant_perms=win_perms,
            deny_perms=win_deny_perms,
            inheritance=win_inheritance,
            reset=win_perms_reset)

    # Cast the vdata according to the vtype
    vdata_decoded = __utils__['reg.cast_vdata'](vdata=vdata, vtype=vtype)

    add_change = {'Key': r'{0}\{1}'.format(hive, key),
                  'Entry': '{0}'.format(salt.utils.stringutils.to_unicode(vname, 'utf-8') if vname else '(Default)'),
                  'Value': vdata_decoded,
                  'Owner': win_owner,
                  'Perms': {'Grant': win_perms,
                            'Deny': win_deny_perms},
                  'Inheritance': win_inheritance}

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

    if ret['result']:
        ret = __utils__['dacl.check_perms'](
            obj_name='\\'.join([hive, key]),
            obj_type='registry32' if use_32bit_registry else 'registry',
            ret=ret,
            owner=win_owner,
            grant_perms=win_perms,
            deny_perms=win_deny_perms,
            inheritance=win_inheritance,
            reset=win_perms_reset)

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


def _imported_parse_reg_file(reg_file):
    r'''
    This is a utility function used by imported_file. This parses a reg file and returns a
    ConfigParser object. A configparser.Error exception will be thrown implicitly
    upon failure to parse.
    '''
    reg_file_fp = io.open(reg_file, "r", encoding="utf-16")
    try:
        reg_file_fp.readline()
        # The first line of a reg file is english text which we must consume before parsing.
        # It contains no data.
        reg_data = configparser.ConfigParser()
        PY2 = sys.version_info[0] == 2
        if PY2:
            reg_data.readfp(reg_file_fp)
        else:
            reg_data.read_file(reg_file_fp)
        return reg_data
    finally:
        reg_file_fp.close()


def _imported_reference_data_wrk(reference_reg_file_url, use_32bit_registry):
    r'''
    This is a utility function used by imported. It does the real work
    for the function _imported_reference_data. It caches the file pointed to by the
    file pointed to with the reference_reg_file_url argument and the parses it.
    It then returns (reference_reg_file, reference_parse, use_32bit_registry)
    where reference_parse is the parser object.
    This information is considered to be the "reference data". It is acquired once
    (here) and the used maximally twice. The first time it is used is when running
    the initial test, and it will be used again if the operation is undertaken
    because a re-test will occur.
    '''
    reference_reg_file = __salt__['cp.cache_file'](reference_reg_file_url)
    if not reference_reg_file:
        error_str = "File/URL '{0}' probably invalid.".format(reference_reg_file_url)
        raise ValueError(error_str)
    reference_parse = _imported_parse_reg_file(reference_reg_file)
    reference_section_count = len(reference_parse.sections())
    if reference_section_count == 0:
        error_str_fmt = "File/URL '{0}' has a section count of 0. It may not be a valid REG file."
        error_str = error_str_fmt.format(reference_reg_file_url)
        raise ValueError(error_str)
    return (reference_reg_file, reference_parse, use_32bit_registry)


def _imported_compose_cmd_execution_err_msg(err):
    r'''
    This is a utility function used by imported. It composes an error message
    based on a CommandExecutionError exception. It is expected that
    the info dictionary of err will have a "command" entry.
    '''
    comment_fmt = "{0}. The attempted command was '{1}'."
    comment = comment_fmt.format(err.message, err.info.get("command", "(Unknown)"))
    return comment


def _imported_reference_data(reference_reg_file_url, use_32bit_registry):
    r'''
    This is a utility function used by imported. It essentially wraps
    imported_reference_data_wrk and it handles some possible exceptions.
    The return value of this function is an ordered pair (A,B).
    The values of A and B are defined as follows:
       A: True if the data is successfully acquired, False otherwise
       B: The reference data, if it has been acquired, otherwise an error message
    '''
    try:
        reference_data \
            = _imported_reference_data_wrk(reference_reg_file_url, use_32bit_registry)
    except ValueError as err:
        comment = str(err)
        return (False, comment)
    except CommandExecutionError as err:
        comment = _imported_compose_cmd_execution_err_msg(err)
        return (False, comment)
    except configparser.Error:
        comment_fmt = "Could not parse file/URL '{0}'. It may not be a valid REG file."
        comment = comment_fmt.format(reference_reg_file_url)
        return (False, comment)
    return (True, reference_data)


def _imported_state_parse(reg_location, use_32bit_registry):
    r'''
    This is a utility function used by imported. This function takes a registry
    location as its primary argument. Using that it exports from the registry location
    (using reg export) to a temporary file and it then parses the file. If reg export
    fails, it raises a CommandExecution error exception. If the function succeeds,
    it returns a parser object representing the registry at the location.
    '''
    if use_32bit_registry:
        word_sz_txt = "32"
    else:
        word_sz_txt = "64"
    present_reg_file = (__salt__['temp.file'])()
    try:
        cmd = 'reg export "{0}" "{1}" /y /reg:{2}'.format(reg_location, present_reg_file, word_sz_txt)
        cmd_ret_dict = __salt__['cmd.run_all'](cmd, python_shell=True)
        retcode = cmd_ret_dict['retcode']
        if retcode != 0:
            cmd_ret_dict['command'] = cmd
            raise CommandExecutionError(
                'reg.exe export failed from registry location {0}'.format(reg_location),
                info=cmd_ret_dict)
        present_data = _imported_parse_reg_file(present_reg_file)
        return present_data
    finally:
        (__salt__['file.remove'])(present_reg_file)

        
def _imported_state_data(reg_location, use_32bit_registry):
    r'''
    This is a utility function used by imported. Its primary argument is a registry location.
    It first tests to see if the location exists in the registry. If it does not,
    it returns None. If the location does exist, this returns a parser object representing
    the registry at the location (by invoking _imported_state_parse).
    '''
    reg_hive = reg_location[:reg_location.index("\\")]
    reg_key_path = reg_location[reg_location.index("\\")+1:]
    if __salt__['reg.key_exists'](reg_hive, reg_key_path, use_32bit_registry):
        state_data = _imported_state_parse(reg_location, use_32bit_registry)
    else:
        state_data = None
    return state_data    
    



def _imported_test_values(reference_parse, state_parse, key_path):
    r'''
    This is a utility function used by imported.
    Tests if or not the set of registry values under key_path in reference_parse
    is a subset of the corresponding set in state_parse.
    Returns True on success and False on failure.
    '''
    reference_items = reference_parse.items(key_path)
    for (reference_option, reference_value) in reference_items:
        if not state_parse.has_option(key_path, reference_option):
            return False
        state_value = state_parse.get(key_path, reference_option)
        if reference_value != state_value:
            return False
    return True


def _imported_test(state_data, reference_data):
    r'''
    This is a utility function used by imported.
    It is intended to test if the present state (as represented by state_data)
    is conformant with the desired state.
    reference_data includes a parser object, and state_data is just a parser object.
    The test just establishes if one is a substructure of the other.
    This function returns True if the test passes, and False if the test fails.
    '''
    (_, reference_parse, _) \
        = reference_data
    state_parse = state_data
    if not state_parse:
        # i.e. state_parse is None because the present state doesn't even
        # have a key at the location.
        return False
    else:
        for key_path in reference_parse.sections():
            if not state_parse.has_section(key_path) \
               or not _imported_test_values(reference_parse, state_parse, key_path):
                return False
    return True


def _imported_do_import(reference_reg_file, use_32bit_registry):
    r'''
    This is a utility function used by imported. This function calls
    the module function reg.import_file. If that function then throws
    exceptions, this function will catch some of them.
    The function returns an ordered pair (A,B).
    The values are defined as follows
       A: Whether or not the operation succeeded expressed as a boolean.
       B: an error message if the operation failed. Otherwise None.
    '''
    try:
        __salt__['reg.import_file'](reference_reg_file, use_32bit_registry)
    except ValueError as err:
        err_msg_fmt = "Call to module function 'reg.import_file' has failed. Error is '{0}'"
        err_msg = comment_fmt.format(str(err))
        return (False, err_msg)
    except CommandExecutionError as err:
        err_msg_fmt = "Call to module function 'reg.import_file' has failed. Error is '{0}'."
        err_msg = comment_fmt.format(err.message)
        return (False, err_msg)
    return (True, None)
    

def _imported_get_change_requirements(reference_data):
    r'''
    This is a utility function used by imported. It's job is to
    determine, using the the reference data, what
    changes are required, and if changes are required an operation
    which will effectuate the changes is also returned.
    Specifically an ordered pair A, B is returned. A and B are defined
    as follows.
           A: If an error occurs the value of A will be False, otherwise True
           B: If an error occurs the value will be an error message,
              otherwise the value will be an ordered pair (c,d). The values
              of c and d are defined as follows.
                 c: This is a dictionary of required changes. It is not a dictionary
                    of changes that have happened.
                 d: If c is non-empty, d will be a function with no paramaters.
                    This function is an operation which will effectuate the changes
                    in the change dictionary.
                    Id c is empty, d will just be None (no operation is needed when no
                    changes are needed). Note that the change dictionary created here 
                    is rather minimal and probably
                    should be fleshed out to include specific changes.
    '''
    (reference_reg_file, reference_parse, use_32bit_registry) \
        = reference_data
    reg_location = (reference_parse.sections())[0]
    try:
        state_parse = _imported_state_data(reg_location, use_32bit_registry)
    except CommandExecutionError as err:
        comment = _imported_compose_cmd_execution_err_msg(err)
        return (False, comment)
    changes = {}
    operation = None
    if not _imported_test(state_parse, reference_data):
        changes['old'] = "Registry unmodified."
        changes['new'] = "Reg file imported."
        operation = lambda : _imported_do_import(reference_reg_file, use_32bit_registry)
    return (True, (changes, operation))


def imported(name, use_32bit_registry=False):
    r'''
    .. versionadded:: Neon

    This is intended to be the stateful correlate of ``reg.import_file``. This will import
    a ``REG`` file (by invoking ``reg.import_file``) only if the import will create changes
    to the registry.

    Args:

        name (str):
            The full path of the ``REG`` file. This can be either a local file
            path or a URL type supported by salt (e.g. ``salt://salt_master_path``)
        use_32bit_registry (bool):
            If the value of this parameter is ``True``, and if the import
            proceeds, the ``REG`` file
            will be imported into the Windows 32 bit registry. Otherwise the
            Windows 64 bit registry will be used.
    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}
    reference_reg_file_url = name
    (result, reference_data) \
        = _imported_reference_data(reference_reg_file_url, use_32bit_registry)
    if not result:
        err_msg = reference_data
        ret['comment'] = err_msg
        ret['result'] = False
        return ret
    # test, get required changes, and compose operation if needed
    (result, pre_operation_data) \
        = _imported_get_change_requirements(reference_data)
    if not result:
        err_msg = pre_operation_data
        ret['comment'] = err_msg
        ret['result'] = False
        return ret
    (pre_operation_required_changes, operation) = pre_operation_data 
    if not pre_operation_required_changes:
        # pre_operation_required_changes is the empty dictionary and we are done
        ret['comment'] = "All data in the reg file is already in the registry. No action taken."
        ret['result'] = True
        return ret
    if __opts__['test']:
        ret['changes'] = pre_operation_required_changes
        ret['comment'] = "Reg file needs to be imported."
        ret['result'] = None
        return ret
    # Required changes is non-empty and we'ere not in test mode so
    # proceed with the operation
    (result, operation_data) = operation()
    if not result:
        # If result is False, that means the operation failed.
        err_msg = operation_data
        ret['comment'] = err_msg
        ret['result'] = False
        return ret
    # retest
    (result, post_operation_data) = _imported_get_change_requirements(reference_data)
    if not result:
        # we met with an error during testing 
        err_msg = post_operation_data
        ret['comment'] = err_msg
        ret['result'] = False
        return ret
    (post_operation_required_changes, _) = post_operation_data
    if post_operation_required_changes:
        # Required change dict is *NOT* the empty dictionary even though it should be.
        err_msg = "Operation appears to have succeeded, but registry is still not in the desired state."
        ret['comment'] = err_msg
        ret['result'] = False
        return ret
    # Report the changes we identified as required before we performed the operation,
    # since success of the retest implies that those changes have happened.
    ret['changes'] = pre_operation_required_changes
    ret['comment'] = "Reg file has been imported."
    ret['result'] = result
    return ret
