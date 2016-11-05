# -*- coding: utf-8 -*-
'''
============
Windows DACL
============
This salt utility contains objects and functions for setting permissions to
objects in Windows. You can use the built in functions or access the objects
directly to create your own custom functionality. There are two objects, Flags
and Dacl.

If you need access only to flags, use the Flags object.

.. code-block:: python

    import salt.utils.win_dacl
    flags = salt.utils.win_dacl.Flags()
    flag_full_control = flags.ace_perms['file']['basic']['full_control']

The Dacl object inherits Flags. To use the Dacl object:

..code-block:: python

    import salt.utils.win_dacl
    dacl = salt.utils.win_dacl.Dacl(obj_type='file')
    dacl.add_ace('Administrators', 'grant', 'full_control')
    dacl.save('C:\\temp')

Object types are used by setting the `obj_type` parameter to a valid Windows
object. Valid object types are as follows:

- file
- service
- printer
- registry
- registry32 (for WOW64)
- share

Each object type has its own set up permissions and 'applies to' properties as
follows. At this time only basic permissions are used for setting. Advanced
permissions are listed for displaying the permissions of an object that don't
match the basic permissions, ie. Special permissions. These should match the
permissions you see when you look at the security for an object.

**Basic Permissions**

    ================  ====  ========  =====  =======  =======
    Permissions       File  Registry  Share  Printer  Service
    ================  ====  ========  =====  =======  =======
    full_control      X     X         X               X
    modify            X
    read_execute      X
    read              X     X         X               X
    write             X     X                         X
    read_write                                        X
    change                            X
    print                                    X
    manage_printer                           X
    manage_documents                         X
    ================  ====  ========  =====  =======  =======

**Advanced Permissions**

    =======================  ====  ========  =======  =======
    Permissions              File  Registry  Printer  Service
    =======================  ====  ========  =======  =======
    list_folder              X
    read_data                X
    create_files             X
    write_data               X
    create_folders           X
    append_data              X
    read_ea                  X
    write_ea                 X
    traverse_folder          X
    execute_file             X
    delete_subfolders_files  X
    read_attributes          X
    write_attributes         X
    delete                   X     X
    read_permissions         X               X        X
    change_permissions       X               X        X
    take_ownership           X               X
    query_value                    X
    set_value                      X
    create_subkey                  X
    enum_subkeys                   X
    notify                         X
    create_link                    X
    read_control                   X
    write_dac                      X
    write_owner                    X
    manage_printer                           X
    print                                    X
    query_config                                      X
    change_config                                     X
    query_status                                      X
    enum_dependents                                   X
    start                                             X
    stop                                              X
    pause_resume                                      X
    interrogate                                       X
    user_defined                                      X
    change_owner                                      X
    =======================  ====  ========  =======  =======

Only the registry and file object types have 'applies to' properties. These
should match what you see when you look at the properties for an object.

    **File types:**

        - this_folder_only: Applies only to this object
        - this_folder_subfolders_files (default): Applies to this object
          and all sub containers and objects
        - this_folder_subfolders: Applies to this object and all sub
          containers, no files
        - this_folder_files: Applies to this object and all file
          objects, no containers
        - subfolders_files: Applies to all containers and objects
          beneath this object
        - subfolders_only: Applies to all containers beneath this object
        - files_only: Applies to all file objects beneath this object

    **Registry types:**

        - this_key_only: Applies only to this key
        - this_key_subkeys: Applies to this key and all subkeys
        - subkeys_only: Applies to all subkeys beneath this object

'''
# Import Python libs
from __future__ import absolute_import

# Import Salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.ext.six.moves import range
import salt.ext.six as six


# Import 3rd-party libs
try:
    import win32security
    import pywintypes
    import salt.utils.win_functions
except ImportError:
    pass


class Flags(object):
    '''
    Object containing all the flags for dealing with Windows permissions
    '''
    # Flag Dicts
    ace_perms = {
        'file': {
            'basic': {
                0x1f01ff: 'Full control',
                0x1301bf: 'Modify',
                0x1201bf: 'Read & execute with write',
                0x1200a9: 'Read & execute',
                0x120089: 'Read',
                0x100116: 'Write',
                'full_control': 0x1f01ff,
                'modify': 0x1301bf,
                'read_execute': 0x1200a9,
                'read': 0x120089,
                'write': 0x100116,
            },
            'advanced': {
                # Advanced
                0x0001: 'List folder / read data',
                0x0002: 'Create files / write data',
                0x0004: 'Create folders / append data',
                0x0008: 'Read extended attributes',
                0x0010: 'Write extended attributes',
                0x0020: 'Traverse folder / execute file',
                0x0040: 'Delete subfolders and files',
                0x0080: 'Read attributes',
                0x0100: 'Write attributes',
                0x10000: 'Delete',
                0x20000: 'Read permissions',
                0x40000: 'Change permissions',
                0x80000: 'Take ownership',
                # 0x100000: 'SYNCHRONIZE',  # This is in all of them
                'list_folder': 0x0001,
                'read_data': 0x0001,
                'create_files': 0x0002,
                'write_data': 0x0002,
                'create_folders': 0x0004,
                'append_data': 0x0004,
                'read_ea': 0x0008,
                'write_ea': 0x0010,
                'traverse_folder': 0x0020,
                'execute_file': 0x0020,
                'delete_subfolders_files': 0x0040,
                'read_attributes': 0x0080,
                'write_attributes': 0x0100,
                'delete': 0x10000,
                'read_permissions': 0x20000,
                'change_permissions': 0x40000,
                'take_ownership': 0x80000,
            },
        },
        'registry': {
            'basic': {
                0xf003f: 'Full Control',
                0x20019: 'Read',
                0x20006: 'Write',
                # Generic Values (These sometimes get hit)
                0x10000000: 'Full Control',
                0x20000000: 'Execute',
                0x40000000: 'Write',
                0xffffffff80000000: 'Read',
                'full_control': 0xf003f,
                'read': 0x20019,
                'write': 0x20006,
            },
            'advanced': {
                # Advanced
                0x0001: 'Query Value',
                0x0002: 'Set Value',
                0x0004: 'Create Subkey',
                0x0008: 'Enumerate Subkeys',
                0x0010: 'Notify',
                0x0020: 'Create Link',
                0x10000: 'Delete',
                0x20000: 'Read Control',
                0x40000: 'Write DAC',
                0x80000: 'Write Owner',
                'query_value': 0x0001,
                'set_value': 0x0002,
                'create_subkey': 0x0004,
                'enum_subkeys': 0x0008,
                'notify': 0x0010,
                'create_link': 0x0020,
                'delete': 0x10000,
                'read_control': 0x20000,
                'write_dac': 0x40000,
                'write_owner': 0x80000,
            },
        },
        'share': {
            'basic': {
                0x1f01ff: 'Full control',
                0x1301bf: 'Change',
                0x1200a9: 'Read',
                'full_control': 0x1f01ff,
                'change': 0x1301bf,
                'read': 0x1200a9,
            },
            'advanced': {},  # No 'advanced' for shares, needed for dict lookup
        },
        'printer': {
            'basic': {
                0x20008: 'Print',
                0xf000c: 'Manage this printer',
                0xf0030: 'Manage documents',
                'print': 0x20008,
                'manage_printer': 0xf000c,
                'manage_documents': 0xf0030,
            },
            'advanced': {
                # Advanced
                0x10004: 'Manage this printer',
                0x0008: 'Print',
                0x20000: 'Read permissions',
                0x40000: 'Change permissions',
                0x80000: 'Take ownership',
                'manage_printer': 0x10004,
                'print': 0x0008,
                'read_permissions': 0x20000,
                'change_permissions': 0x40000,
                'take_ownership': 0x80000,
            },
        },
        'service': {
            'basic': {
                0xf01ff: 'Full Control',
                0x2008f: 'Read & Write',
                0x2018d: 'Read',
                0x20002: 'Write',
                'full_control': 0xf01ff,
                'read_write': 0x2008f,
                'read': 0x2018d,
                'write': 0x20002,
            },
            'advanced': {
                0x0001: 'Query Config',
                0x0002: 'Change Config',
                0x0004: 'Query Status',
                0x0008: 'Enumerate Dependents',
                0x0010: 'Start',
                0x0020: 'Stop',
                0x0040: 'Pause/Resume',
                0x0080: 'Interrogate',
                0x0100: 'User-Defined Control',
                # 0x10000: 'Delete',  # Not visible in the GUI
                0x20000: 'Read Permissions',
                0x40000: 'Change Permissions',
                0x80000: 'Change Owner',
                'query_config': 0x0001,
                'change_config': 0x0002,
                'query_status': 0x0004,
                'enum_dependents': 0x0008,
                'start': 0x0010,
                'stop': 0x0020,
                'pause_resume': 0x0040,
                'interrogate': 0x0080,
                'user_defined': 0x0100,
                'read_permissions': 0x20000,
                'change_permissions': 0x40000,
                'change_owner': 0x80000,
            },
        }
    }

    ace_prop = {
        'file': {
            # for report
            0x0000: 'Not Inherited (file)',
            0x0001: 'This folder and files',
            0x0002: 'This folder and subfolders',
            0x0003: 'This folder, subfolders and files',
            0x0006: 'This folder only',
            0x0009: 'Files only',
            0x000a: 'Subfolders only',
            0x000b: 'Subfolders and files only',
            0x0010: 'Inherited (file)',
            # for setting
            'this_folder_only': 0x0006,
            'this_folder_subfolders_files': 0x0003,
            'this_folder_subfolders': 0x0002,
            'this_folder_files': 0x0001,
            'subfolders_files': 0x000b,
            'subfolders_only': 0x000a,
            'files_only': 0x0009,
        },
        'registry': {
            0x0000: 'Not Inherited',
            0x0002: 'This key and subkeys',
            0x0006: 'This key only',
            0x000a: 'Subkeys only',
            0x0010: 'Inherited',
            'this_key_only': 0x0006,
            'this_key_subkeys': 0x0002,
            'subkeys_only': 0x000a,
        },
        'registry32': {
            0x0000: 'Not Inherited',
            0x0002: 'This key and subkeys',
            0x0006: 'This key only',
            0x000a: 'Subkeys only',
            0x0010: 'Inherited',
            'this_key_only': 0x0006,
            'this_key_subkeys': 0x0002,
            'subkeys_only': 0x000a,
        },
    }

    ace_type = {
        'grant': win32security.ACCESS_ALLOWED_ACE_TYPE,
        'deny': win32security.ACCESS_DENIED_ACE_TYPE,
        win32security.ACCESS_ALLOWED_ACE_TYPE: 'grant',
        win32security.ACCESS_DENIED_ACE_TYPE: 'deny',
    }

    element = {
        'dacl': win32security.DACL_SECURITY_INFORMATION,
        'group': win32security.GROUP_SECURITY_INFORMATION,
        'owner': win32security.OWNER_SECURITY_INFORMATION,
    }

    inheritance = {
        'protected': win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        'unprotected': win32security.UNPROTECTED_DACL_SECURITY_INFORMATION,
    }

    obj_type = {
        'file': win32security.SE_FILE_OBJECT,
        'service': win32security.SE_SERVICE,
        'printer': win32security.SE_PRINTER,
        'registry': win32security.SE_REGISTRY_KEY,
        'registry32': win32security.SE_REGISTRY_WOW64_32KEY,
        'share': win32security.SE_LMSHARE,
    }


class Dacl(Flags):
    '''
    DACL Object
    '''
    def __init__(self, obj_name=None, obj_type='file'):
        '''
        Either load the DACL from the passed object or create an empty DACL. If
        `obj_name` is not passed, an empty DACL is created.

        Args:
            obj_name (str): The full path to the object. If None, a blank DACL
            will be created

            obj_type (Optional[str]): The type of object.

        Returns:
            obj: A DACL object

        Usage:

        .. code-block:: python

            # Create an Empty DACL
            dacl = Dacl(obj_type=obj_type)

            # Load the DACL of the named object
            dacl = Dacl(obj_name, obj_type)
        '''
        self.dacl_type = obj_type.lower()
        if obj_name is None:
            self.dacl = win32security.ACL()
        else:
            if self.dacl_type in ['registry', 'registry32']:
                obj_name = self.get_reg_name(obj_name)

            sd = win32security.GetNamedSecurityInfo(
                obj_name, self.obj_type[self.dacl_type], self.element['dacl'])
            self.dacl = sd.GetSecurityDescriptorDacl()
            if self.dacl is None:
                self.dacl = win32security.ACL()

    def get_reg_name(self, obj_name):
        '''
        Take the obj_name and convert the hive to a valid registry hive.

        Args:

            obj_name (str): The full path to the registry key including the
            hive, eg: ``HKLM\\SOFTWARE\\salt``. Valid options for the hive are:

            - HKEY_LOCAL_MACHINE
            - MACHINE
            - HKLM
            - HKEY_USERS
            - USERS
            - HKU
            - HKEY_CURRENT_USER
            - CURRENT_USER
            - HKCU
            - HKEY_CLASSES_ROOT
            - CLASSES_ROOT
            - HKCR

        Returns:
            str: The full path to the registry key in the format expected by
            the Windows API

        Usage:

        .. code-block:: python

            import salt.utils.win_dacl
            dacl = salt.utils.win_dacl.Dacl()
            valid_key = dacl.get_reg_name('HKLM\\SOFTWARE\\salt')

            # Returns: MACHINE\\SOFTWARE\\salt
        '''
        # Make sure the hive is correct
        # Should be MACHINE, USERS, CURRENT_USER, or CLASSES_ROOT
        hives = {
            # MACHINE
            'HKEY_LOCAL_MACHINE': 'MACHINE',
            'MACHINE': 'MACHINE',
            'HKLM': 'MACHINE',
            # USERS
            'HKEY_USERS': 'USERS',
            'USERS': 'USERS',
            'HKU': 'USERS',
            # CURRENT_USER
            'HKEY_CURRENT_USER': 'CURRENT_USER',
            'CURRENT_USER': 'CURRENT_USER',
            'HKCU': 'CURRENT_USER',
            # CLASSES ROOT
            'HKEY_CLASSES_ROOT': 'CLASSES_ROOT',
            'CLASSES_ROOT': 'CLASSES_ROOT',
            'HKCR': 'CLASSES_ROOT',
        }
        reg = obj_name.split('\\')
        passed_hive = reg.pop(0)

        try:
            valid_hive = hives[passed_hive.upper()]
        except KeyError:
            raise CommandExecutionError(
                'Invalid Registry Hive: {0}'.format(passed_hive))

        reg.insert(0, valid_hive)

        return r'\\'.join(reg)

    def add_ace(self, principal, access_mode, permission, applies_to):
        '''
        Add an ACE to the DACL

        Args:

            principal (str): The sid of the user/group to for the ACE

            access_mode (str): Determines the type of ACE to add. Must be either
            ``grant`` or ``deny``.

            permission (str): The type of permissions to grant/deny the user.

            applies_to (str): The objects to which these permissions will apply.
            Not all these options apply to all object types.

        Returns:
            bool: True if successful, otherwise False

        Usage:

        .. code-block:: python

            dacl = Dacl(obj_type=obj_type)
            dacl.add_ace(sid, access_mode, applies_to, permission)
            dacl.save(obj_name, protected)
        '''
        sid = get_sid(principal)

        if self.dacl is None:
            raise SaltInvocationError(
                'You must load the DACL before adding an ACE')

        # Add ACE to the DACL
        # Grant or Deny
        try:
            if access_mode.lower() == 'grant':
                self.dacl.AddAccessAllowedAceEx(
                    win32security.ACL_REVISION_DS,
                    self.ace_prop[self.dacl_type][applies_to],
                    self.ace_perms[self.dacl_type]['basic'][permission],
                    sid)
            elif access_mode.lower() == 'deny':
                self.dacl.AddAccessDeniedAceEx(
                    win32security.ACL_REVISION_DS,
                    self.ace_prop[self.dacl_type][applies_to],
                    self.ace_perms[self.dacl_type]['basic'][permission],
                    sid)
            else:
                raise SaltInvocationError(
                    'Invalid access mode: {0}'.format(access_mode))
        except Exception as exc:
            return False, 'Error: {0}'.format(str(exc))

        return True

    def get_ace(self, principal, return_obj=False):
        '''
        Get the ACE for a specific principal.

        Args:

            principal (str): The name of the user or group for which to get the
            ace. Can also be a SID.

            return_obj (bool): Return the ACE object instead of a dict. Will
            return the first ACE that matches the principal.

        Returns:
            dict: A dictionary containing the ACEs found for the principal

        Usage:

        .. code-block:: python

            dacl = Dacl(obj_type=obj_type)
            dacl.get_ace()
        '''
        sid = get_sid(principal)

        ret = {}

        for i in range(0, self.dacl.GetAceCount()):
            ace = self.dacl.GetAce(i)

            # Parse the ACE to text if it matches the passed SID or if
            if ace[2] == sid:
                # Return the ACE if it matches the passed SID
                if return_obj:
                    return ace
                user, a_type, a_prop, a_perms, inh = \
                    self._ace_to_dict(ace)
                if user in ret:
                    if a_type in ret[user]:
                        if a_prop and a_prop not in ret[user][a_type]['applies to']:
                            if ret[user][a_type]['applies to'] == 'Not Inherited':
                                ret[user][a_type]['applies to'] = a_prop
                            else:
                                a_prop = ':{0}'.format(a_prop)
                                ret[user][a_type]['applies to'] += a_prop
                        for perm in a_perms:
                            if perm and perm not in ret[user][a_type]['permissions']:
                                ret[user][a_type]['permissions'].extend(a_perms)
                else:
                    ret.update(
                        {user: {
                            a_type: {
                                'applies to': a_prop,
                                'inherited': inh,
                                'permissions': a_perms,
                            }}}
                    )

        return ret

    def list_aces(self):
        '''
        List all Entries in the dacl.

        Returns:
            dict: A dictionary containing the ACEs for the object

        Usage:

        .. code-block:: python

            dacl = Dacl('C:\\Temp')
            dacl.list_aces()
        '''
        ret = {}

        # loop through each ACE in the DACL
        for i in range(0, self.dacl.GetAceCount()):
            ace = self.dacl.GetAce(i)

            # Get ACE Elements
            user, a_type, a_prop, a_perms, inh = self._ace_to_dict(ace)

            # Check for existing entries in the return
            if user in ret and a_type in ret[user]:

                # Check for an existing applies to entry
                if a_prop and a_prop not in ret[user][a_type]['applies to']:
                    if ret[user][a_type]['applies to'] == 'Not Inherited':
                        ret[user][a_type]['applies to'] = a_prop
                    else:
                        a_prop = ':{0}'.format(a_prop)
                        ret[user][a_type]['applies to'] += a_prop

                # Go through each permission
                for perm in a_perms:
                    # If the permission is not in the ret, add it
                    if perm and perm not in ret[user][a_type]['permissions']:
                        ret[user][a_type]['permissions'].extend(a_perms)

                # Set inherited bit
                if inh and not ret[user][a_type]['inherited']:
                    ret[user][a_type]['inherited'] = inh

            else:
                # First time through
                ret.update(
                    {user: {
                        a_type: {
                            'applies to': a_prop,
                            'inherited': inh,
                            'permissions': a_perms,
                        }}}
                )

        return ret

    def _ace_to_dict(self, ace):
        '''
        Helper function for creating the ACE return dictionary
        '''
        # Get the principal from the sid (object sid)
        sid = win32security.ConvertSidToStringSid(ace[2])
        principal = get_name(sid)

        # Get the ace type
        ace_type = self.ace_type[ace[0][0]]

        # Is the inherited ace flag present
        inherited = ace[0][1] & win32security.INHERITED_ACE == 16

        # Ace Propagation
        ace_prop = 'NA'

        # Get the ace propagation properties
        if self.dacl_type in ['file', 'registry', 'registry32']:

            ace_prop = ace[0][1]

            # Remove the inherited ace flag and get propagation
            if inherited:
                ace_prop = ace[0][1] ^ win32security.INHERITED_ACE

            # Lookup the propagation
            try:
                ace_prop = self.ace_prop[self.dacl_type][ace_prop]
            except KeyError:
                ace_prop = 'Unknown propagation'

        # Get the object type
        obj_type = 'registry' if self.dacl_type == 'registry32' \
            else self.dacl_type

        # Get the ace permissions
        # Check basic permissions first
        ace_perms = [self.ace_perms[obj_type]['basic'].get(ace[1], [])]

        # If it didn't find basic perms, check advanced permissions
        if not ace_perms[0]:
            ace_perms = []
            for perm in self.ace_perms[obj_type]['advanced']:
                # Don't match against the string perms
                if isinstance(perm, six.string_types):
                    continue
                if ace[1] & perm == perm:
                    ace_perms.append(
                        self.ace_perms[obj_type]['advanced'][perm])

        # If still nothing, it must be undefined
        if not ace_perms[0]:
            ace_perms = ['Undefined Permission: {0}'.format(ace[1])]

        return principal, ace_type, ace_prop, ace_perms, inherited

    def rm_ace(self, principal, ace_type='all'):
        '''
        Remove a specific ACE from the DACL.

        Args:

            principal (str): The user whose ACE to remove. Can be the user name
            or a SID.

            ace_type (str): The type of ACE to remove. If not specified, all
            ACEs will be removed. Default is 'all'. Valid options are:

                - 'grant'
                - 'deny'
                - 'all'

        Returns:
            list: List of removed aces

        Usage:

        .. code-block:: python

            dacl = Dacl(obj_name='C:\\temp', obj_type='file')
            dacl.rm_ace('Users')
            dacl.save(obj_name='C:\\temp')
        '''
        sid = get_sid(principal)
        offset = 0
        ret = []
        for i in range(0, self.dacl.GetAceCount()):
            ace = self.dacl.GetAce(i - offset)
            if ace[2] == sid:
                if self.ace_type[ace[0][0]] == ace_type.lower() or \
                        ace_type == 'all':
                    self.dacl.DeleteAce(i - offset)
                    ret.append(self._ace_to_dict(ace))
                    offset += 1

        if not ret:
            ret = ['ACE not found for {0}'.format(principal)]

        return ret

    def save(self, obj_name, protected=None):
        '''
        Save the DACL

        obj_name (str): The object for which to set permissions. This can be the
        path to a file or folder, a registry key, printer, etc. For more
        information about how to format the name see:

        https://msdn.microsoft.com/en-us/library/windows/desktop/aa379593(v=vs.85).aspx

        protected (Optional[bool]): True will disable inheritance for the
        object. False will enable inheritance. None will make no change. Default
        is None.

        Returns:
            bool: True if successful, Otherwise raises an exception

        Usage:

        .. code-block:: python

            dacl = Dacl(obj_type='file')
            dacl.save('C:\\Temp', True)
        '''
        sec_info = self.element['dacl']

        if protected is not None:
            if protected:
                sec_info = sec_info | self.inheritance['protected']
            else:
                sec_info = sec_info | self.inheritance['unprotected']

        if self.dacl_type in ['registry', 'registry32']:
            obj_name = self.get_reg_name(obj_name)

        try:
            win32security.SetNamedSecurityInfo(
                obj_name,
                self.obj_type[self.dacl_type],
                sec_info,
                None, None, self.dacl, None)
        except pywintypes.error as exc:
            raise CommandExecutionError(
                'Failed to set permissions: {0}'.format(exc[2]))

        return True


def get_sid(principal):
    '''
    Converts a username to a sid, or verifies a sid. Required for working with
    the DACL.

    Args:

        principal(str): The principal to lookup the sid. Can be a sid or a
        username.

    Returns:
        PySID Object: A sid

    Usage:

    .. code-block:: python

        # Get a user's sid
        salt.utils.win_dacl.get_sid('jsnuffy')

        # Verify that the sid is valid
        salt.utils.win_dacl.get_sid('S-1-5-32-544')
    '''
    # Test if the user passed a sid or a name
    try:
        sid = salt.utils.win_functions.get_sid_from_name(principal)
    except CommandExecutionError:
        sid = principal

    # Test if the SID is valid
    try:
        sid = win32security.ConvertStringSidToSid(sid)
    except pywintypes.error:
        raise CommandExecutionError(
            'Invalid user/group or sid: {0}'.format(principal))
    except TypeError:
        raise CommandExecutionError

    return sid


def get_sid_string(principal):
    '''
    Converts a PySID object to a string SID.

    Args:

        principal(str): The principal to lookup the sid. Must be a PySID object.

    Returns:
        str: A sid

    Usage:

    .. code-block:: python

        # Get a PySID object
        py_sid = salt.utils.win_dacl.get_sid('jsnuffy')

        # Get the string version of the SID
        salt.utils.win_dacl.get_sid_string(py_sid)
    '''
    try:
        return win32security.ConvertSidToStringSid(principal)
    except TypeError:
        # Not a PySID object
        principal = get_sid(principal)

    try:
        return win32security.ConvertSidToStringSid(principal)
    except pywintypes.error:
        raise CommandExecutionError('Invalid principal {0}'.format(principal))


def get_name(sid):
    '''
    Gets the name from the specified SID. Opposite of get_sid

    Args:
        sid (str): The SID for which to find the name

    Returns:
        str: The name that corresponds to the passed SID

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.get_name('S-1-5-32-544')
    '''
    try:
        sid_obj = win32security.ConvertStringSidToSid(sid)
        name = win32security.LookupAccountSid(None, sid_obj)[0]
    except pywintypes.error as exc:
        raise CommandExecutionError(
            'User {0} found: {1}'.format(sid, exc[2]))

    return name


def get_owner(obj_name):
    '''
    Gets the owner of the passed object

    Args:
        obj_name (str): The path for which to obtain owner information

    Returns:
        str: The owner (group or user)

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.get_owner('c:\\file')
    '''
    # Return owner
    security_descriptor = win32security.GetFileSecurity(
        obj_name, win32security.OWNER_SECURITY_INFORMATION)
    owner_sid = security_descriptor.GetSecurityDescriptorOwner()

    return get_name(win32security.ConvertSidToStringSid(owner_sid))


def set_owner(obj_name, principal, obj_type='file'):
    '''
    Set the owner of an object. This can be a file, folder, registry key,
    printer, service, etc...

    Args:

        obj_name (str): The object for which to set owner. This can be the path
        to a file or folder, a registry key, printer, etc. For more information
        about how to format the name see:

        https://msdn.microsoft.com/en-us/library/windows/desktop/aa379593(v=vs.85).aspx

        principal (str): The name of the user or group to make owner of the
        object. Can also pass a SID.

        obj_type (Optional[str]): The type of object for which to set the owner.

    Returns:
        bool: True if successful, raises an error otherwise

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.set_owner('C:\\MyDirectory', 'jsnuffy', 'file')
    '''
    sid = get_sid(principal)

    flags = Flags()

    # Set the user
    try:
        win32security.SetNamedSecurityInfo(
            obj_name,
            flags.obj_type[obj_type],
            flags.element['owner'],
            sid,
            None, None, None)
    except pywintypes.error as exc:
        raise CommandExecutionError(
            'Failed to set owner: {0}'.format(exc[2]))

    return True


def set_permissions(obj_name,
                    principal,
                    permission,
                    access_mode='grant',
                    reset_perms=False,
                    obj_type='file',
                    protected=None,
                    applies_to='this_folder_subfolders_files'):
    '''
    Set the permissions of an object. This can be a file, folder, registry key,
    printer, service, etc...

    Args:

        obj_name (str): The object for which to set permissions. This can be the
        path to a file or folder, a registry key, printer, etc. For more
        information about how to format the name see:

        https://msdn.microsoft.com/en-us/library/windows/desktop/aa379593(v=vs.85).aspx

        obj_type (Optional[str]): The type of object for which to set
        permissions.

        principal (str): The name of the user or group for which to set
        permissions. Can also pass a SID.

        permission (str): The type of permissions to grant/deny the user.

        access_mode (Optional[str]): Whether to grant or deny user the access.
        Valid options are:

            - grant (default): Grants the user access
            - deny: Denies the user access

        reset_perms (Optional[bool]): True will overwrite the permissions on the
        specified object. False will append the permissions. Default is False

        protected (Optional[bool]): True will disable inheritance for the
        object. False will enable inheritance. None will make no change. Default
        is None.

        applies_to (Optional[str]): The objects to which these permissions will
        apply. Not all these options apply to all object types. Valid options:

    Returns:
        bool: True if successful, raises an error otherwise

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.set_permissions(
            'C:\\Temp', 'file', 'jsnuffy', 'full_control')
    '''
    # If you don't pass `obj_name` it will create a blank DACL
    # Otherwise, it will grab the existing DACL and add to it
    if reset_perms:
        dacl = Dacl(obj_type=obj_type)
    else:
        dacl = Dacl(obj_name, obj_type)
        dacl.rm_ace(principal, access_mode)

    dacl.add_ace(principal, access_mode, permission, applies_to)
    dacl.save(obj_name, protected)

    return True


def rm_permissions(obj_name,
                   principal,
                   ace_type='all',
                   obj_type='file'):
    r'''
    Remove a user's ACE from an object. This can be a file, folder, registry
    key, printer, service, etc...

    Args:

        obj_name (str): The object from which to remove the ace. This can be the
        path to a file or folder, a registry key, printer, etc. For more
        information about how to format the name see:

        https://msdn.microsoft.com/en-us/library/windows/desktop/aa379593(v=vs.85).aspx

        principal (str): The name of the user or group for which to set
        permissions. Can also pass a SID.

        ace_type(Optional[str]): The type of ace to remove. There are two types
        of ACEs, 'grant' and 'deny'. 'all' will remove all ACEs for the user.

        obj_type (Optional[str]): The type of object for which to set
        permissions.

    Returns:
        bool: True if successful, raises an error otherwise

    Usage:

    .. code-block:: python

        # Remove jsnuffy's grant ACE from C:\Temp
        salt.utils.win_dacl.rm_permissions(
            'C:\\Temp', 'jsnuffy', 'grant', 'file')

        # Remove all ACEs for jsnuffy from C:\Temp
        salt.utils.win_dacl.rm_permissions('C:\\Temp', 'jsnuffy')
    '''
    dacl = Dacl(obj_name, obj_type)

    dacl.rm_ace(principal, ace_type)
    dacl.save(obj_name)

    return True


def get_permissions(obj_name, principal=None, obj_type='file'):
    '''
    Get the permissions for the passed object

    Args:

        obj_name (str): The name of or path to the object.

        obj_type (str): The type of object for which to get permissions.

        principal (str): The name of the user or group for which to get
        permissions. Can also pass a SID.

    Returns:
        dict: A dictionary representing the object permissions

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.get_permissions('C:\\Temp')
    '''
    dacl = Dacl(obj_name, obj_type)

    if principal is None:
        return dacl.list_aces()

    return dacl.get_ace(principal)


def has_permission(obj_name,
                   obj_type,
                   principal,
                   permission,
                   access_mode='grant',
                   exact=True):
    r'''
    Check if the object has a permission

    Args:

        obj_name (str): The name of or path to the object.

        obj_type (str): The type of object for which to check permissions.

        principal (str): The name of the user or group for which to get
        permissions. Can also pass a SID.

        permission (str): The permission to verify. Valid options depend on the
        obj_type.

        access_mode (Optional[str]): The access mode to check. Is the user
        granted or denied the permission. Default is 'grant'. Valid options are:

            - grant
            - deny

        exact (bool): True for an exact match, otherwise check to see if the
        permission is included in the ACE

    Returns:
        bool: True if the object has the permission, otherwise False

    Usage:

    .. code-block:: python

        # Does Joe have read permissions to C:\Temp
        salt.utils.win_dacl.has_permission('C:\\Temp', 'file', 'joe', 'read', 'grant', False)

        # Does Joe have Full Control of C:\Temp
        salt.utils.win_dacl.has_permission('C:\\Temp', 'file', 'joe', 'full_control', 'grant')
    '''
    # Validate obj_type
    if obj_type.lower() not in ['file', 'service', 'printer', 'registry',
                                'registry32', 'share']:
        raise SaltInvocationError(
            'Invalid "obj_type" passed: {0}'.format(obj_type))
    obj_type = obj_type.lower()

    # Validate inherited
    # Validate access_mode
    if access_mode.lower() not in ['grant', 'deny']:
        raise SaltInvocationError(
            'Invalid "access_mode" passed: {0}'.format(access_mode))
    access_mode = access_mode.lower()

    # Get the DACL
    dacl = Dacl(obj_name, obj_type)

    # Get a PySID object
    sid = get_sid(principal)

    # Get the passed permission flag, check basic first
    chk_flag = dacl.ace_perms[obj_type]['basic'].get(
        permission.lower(),
        dacl.ace_perms[obj_type]['advanced'].get(permission.lower(), False))
    if not chk_flag:
        raise SaltInvocationError(
            'Invalid "permission" passed: {0}'.format(permission))

    # Check each ace for sid and type
    cur_flag = None
    for i in range(0, dacl.dacl.GetAceCount()):
        ace = dacl.dacl.GetAce(i)
        if ace[2] == sid and dacl.ace_type[ace[0][0]] == access_mode:
            cur_flag = ace[1]

    # If the ace is empty, return false
    if not cur_flag:
        return False

    # Check for the exact permission in the ACE
    if exact:
        return chk_flag == cur_flag

    # Check if the ACE contains the permission
    return cur_flag & chk_flag == chk_flag


def set_inheritance(obj_name, enabled, obj_type='file', clear=False):
    '''
    Enable or disable an objects inheritance.

    Args:

        obj_name (str): The name of the object

        enabled (bool): True to enable inheritance, False to disable

        obj_type (Optional[str]): The type of object. Only three objects allow
        inheritance. Valid objects are:

            - file (default): This is a file or directory
            - registry
            - registry32 (for WOW64)

        clear (Optional[bool]): True to clear existing ACEs, False to keep
        existing ACEs

    Returns:
        bool: True if successful, otherwise an Error

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.set_inheritance('C:\\Temp', False)
    '''
    if obj_type not in ['file', 'registry', 'registry32']:
        raise SaltInvocationError(
            'obj_type called with incorrect parameter: {0}'.format(obj_name))

    if clear:
        dacl = Dacl(obj_type=obj_type)
    else:
        dacl = Dacl(obj_name, obj_type)

    return dacl.save(obj_name, not enabled)


def get_inheritance(obj_name, obj_type='file'):
    '''
    Get an objects inheritance.

    Args:

        obj_name (str): The name of the object

        obj_type (Optional[str]): The type of object. Only three object types
        allow inheritance. Valid objects are:

            - file (default): This is a file or directory
            - registry
            - registry32 (for WOW64)

            The following should return False as there is no inheritance:

            - service
            - printer
            - share

    Returns:
        bool: True if enabled, otherwise False

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.get_inheritance('HKLM\\SOFTWARE\\salt', 'registry')
    '''
    dacl = Dacl(obj_name, obj_type)
    inherited = win32security.INHERITED_ACE

    for i in range(0, dacl.dacl.GetAceCount()):
        ace = dacl.dacl.GetAce(i)
        if ace[0][1] & inherited == inherited:
            return True

    return False
