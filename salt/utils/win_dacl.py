# -*- coding: utf-8 -*-
'''
Functions for setting permissions to objects in windows
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt libs
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Import 3rd-party libs
try:
    import ntsecuritycon
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
    obj_type = {
        'file': win32security.SE_FILE_OBJECT,
        'service': win32security.SE_SERVICE,
        'printer': win32security.SE_PRINTER,
        'registry': win32security.SE_REGISTRY_KEY,
        'registry32': win32security.SE_REGISTRY_WOW64_32KEY,
        'share': win32security.SE_LMSHARE}

    element = {
        'dacl': win32security.DACL_SECURITY_INFORMATION,
        'group': win32security.GROUP_SECURITY_INFORMATION,
        'owner': win32security.OWNER_SECURITY_INFORMATION}

    dacl_inheritance = {
        'protected': win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        'unprotected': win32security.UNPROTECTED_DACL_SECURITY_INFORMATION}

    access = {
        'full_control':
            ntsecuritycon.GENERIC_ALL,
        'modify':
            ntsecuritycon.GENERIC_READ |
            ntsecuritycon.GENERIC_WRITE |
            ntsecuritycon.GENERIC_EXECUTE |
            ntsecuritycon.DELETE,
        'read_execute':
            ntsecuritycon.GENERIC_READ |
            ntsecuritycon.GENERIC_EXECUTE,
        'read':
            ntsecuritycon.GENERIC_READ,
        'write':
            ntsecuritycon.GENERIC_WRITE}

    applies_to = {
        'this_folder_only':
            win32security.CONTAINER_INHERIT_ACE |
            win32security.NO_PROPAGATE_INHERIT_ACE,
        'this_folder_subfolders_files':
            win32security.CONTAINER_INHERIT_ACE |
            win32security.OBJECT_INHERIT_ACE,
        'this_folder_subfolders':
            win32security.CONTAINER_INHERIT_ACE,
        'this_folder_files':
            win32security.OBJECT_INHERIT_ACE,
        'subfolders_files':
            win32security.CONTAINER_INHERIT_ACE |
            win32security.OBJECT_INHERIT_ACE |
            win32security.INHERIT_ONLY_ACE,
        'subfolders_only':
            win32security.CONTAINER_INHERIT_ACE |
            win32security.INHERIT_ONLY_ACE,
        'files_only':
            win32security.OBJECT_INHERIT_ACE |
            win32security.INHERIT_ONLY_ACE}

    def type_flags(self, name):
        '''
        Get the flag that designates the type of object passed
        '''
        try:
            return self.obj_type[name.lower()]
        except KeyError:
            raise CommandExecutionError(
                'Invalid object type: {0}'.format(name))

    def element_flags(self, name):
        '''
        Get the flag for the element of the security information object to be
        returned/set
        '''
        try:
            return self.element[name.lower()]
        except KeyError:
            raise CommandExecutionError(
                'Invalid security info element: {0}'.format(name))

    def dacl_inheritance_flags(self, name):
        '''
        Get the flag that determines whether the object will inherit parent
        permissions
        '''
        try:
            return self.dacl_inheritance[name.lower()]
        except KeyError:
            raise CommandExecutionError(
                'Invalid inheritance: {0}'.format(name))

    def permission_flags(self, name):
        '''
        Get the flags that correspond to the desired permissions
        '''
        try:
            return self.access[name.lower()]
        except KeyError:
            raise CommandExecutionError(
                'Invalid access: {0}'.format(name))

    def applies_to_flags(self, name):
        '''
        Get the flags that determine the type of objects to which the DACL
        applies
        '''
        try:
            return self.applies_to[name.lower()]
        except KeyError:
            raise CommandExecutionError(
                'Invalid applies_to: {0}'.format(name))


class Dacl(Flags):
    '''
    DACL Object
    '''
    def __init__(self, obj_name=None, obj_type='file'):
        '''
        Either load the DACL from the passed object or create an empty DACL. If
        `obj_name` is not passed, an empty DACL is created.

        Args:
            obj_name (str):
                The full path to the object. If None, a blank DACL will be
                created

            obj_type (Optional[str]):
                The type of object. Valid options are:

                - file (default): This is a file or directory
                - service
                - printer
                - registry
                - registry32 (for WOW64)
                - share

        Returns:
            obj: A DACL object

        Usage:

            # Create an Empty DACL
            dacl = DACL(obj_type=obj_type)

            # Load the DACL of the named object
            dacl = DACL(obj_name, obj_type)
        '''
        if obj_name is None:
            self.dacl = win32security.ACL()
        else:
            sd = win32security.GetNamedSecurityInfo(
                obj_name, self.type_flags(obj_type), self.element_flags('dacl'))
            self.dacl = sd.GetSecurityDescriptorDacl()
            if self.dacl is None:
                self.dacl = win32security.ACL()

    def add_ace(self, sid, access_mode, applies_to, permission):
        '''
        Add an ACE to the DACL

        Args:

            sid (str):
                The sid of the user/group to for the ACE

            access_mode (str):
                Determines the type of ACE to add. Must be either `grant` or
                `deny`.

            applies_to (str):
                The objects to which these permissions will apply. Not all these
                options apply to all object types. Valid options are:

                - this_folder_only
                - this_folder_subfolders_files
                - this_folder_subfolders
                - this_folder_files
                - subfolders_files
                - subfolders_only
                - files_only

            permission (str):
                The type of permissions to grant/deny the user. Valid options:

                - full_control
                - modify
                - read_execute
                - read
                - write

        Returns:
            bool: True if successful

        Usage:

            dacl = DACL(obj_type=obj_type)
            dacl.add_ace(sid, access_mode, applies_to, permission)
            dacl.save(obj_name, obj_type, protected)
        '''
        if self.dacl is None:
            raise SaltInvocationError(
                'You must load the DACL before adding and ACE')

        # Add ACE to the DACL
        # Grand or Deny
        try:
            if access_mode.lower() == 'grant':
                self.dacl.AddAccessAllowedAceEx(
                    win32security.ACL_REVISION_DS,
                    self.applies_to_flags(applies_to),
                    self.permission_flags(permission),
                    sid)
            elif access_mode.lower() == 'deny':
                self.dacl.AddAccessDeniedAceEx(
                    win32security.ACL_REVISION_DS,
                    self.applies_to_flags(applies_to),
                    self.permission_flags(permission),
                    sid)
            else:
                raise SaltInvocationError(
                    'Invalid access mode: {0}'.format(access_mode))
        except Exception as exc:
            return False, 'Error: {0}'.format(str(exc))

        return True

    def get_ace(self):
        '''
        Get the ACE for the DACL

        Returns:
            dict: A dictionary containing the ACE for the object
        Usage:

            dacl = DACL(obj_type=obj_type)
            dacl.get_ace()
        '''
        return self.dacl.GetAce(0)

    def save(self, obj_name, obj_type, protected=None):
        '''
        Save the dacl

        obj_name (str):
            The object for which to set permissions. This can be the path to a
            file or folder, a registry key, printer, etc. For more information
            about how to format the name see:
            https://msdn.microsoft.com/en-us/library/windows/desktop/aa379593(v=vs.85).aspx

        obj_type (str):
            The type of object for which to set permissions. Valid objects are
            as follows:

            - file (default): This is a file or directory
            - service
            - printer
            - registry
            - registry32 (for WOW64)
            - share

        protected (Optional[bool]):
            True will disable inheritance for the object. False will enable
            inheritance. None will make no change. Default is None.

        Returns:
            bool: True if successful, Otherwise raises an exception

        Usage:
            dacl = DACL(obj_type=obj_type)
            dacl.save(obj_name, obj_type, protected)
        '''
        sec_info = self.element_flags('dacl')
        if protected is not None:
            if protected:
                sec_info = sec_info | self.dacl_inheritance_flags('protected')
            else:
                sec_info = sec_info | self.dacl_inheritance_flags('unprotected')

        try:
            win32security.SetNamedSecurityInfo(
                obj_name,
                self.type_flags(obj_type),
                sec_info,
                None, None, self.dacl, None)
        except pywintypes.error as exc:
            raise CommandExecutionError(
                'Failed to set permissions: {0}'.format(exc[2]))

        return True


def get_sid(principal):
    '''
    Converts a username to a sid, or verifies a sid.

    Args:
        principal(str):
            The principal to lookup the sid. Can be a sid or a username.

    Returns:
        str: A sid

    Usage:
        salt.utils.dacl.get_sid('jsnuffy')
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

    return sid


def get_name(sid):
    '''
    Gets the name from the specified SID. Opposite of get_sid

    Args:
        sid (str): The SID for which to find the name

    Returns:
        str: The name that corresponds to the passed SID
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

        obj_name (str):
            The object for which to set owner. This can be the path to a file or
            folder, a registry key, printer, etc. For more information about how
            to format the name see:
            https://msdn.microsoft.com/en-us/library/windows/desktop/aa379593(v=vs.85).aspx

        principal (str):
            The name of the user or group to make owner of the object. Can also
            pass a SID.

        obj_type (Optional[str]):
            The type of object for which to set the owner. Valid objects are as
            follows:

            - file (default): This is a file or directory
            - service
            - printer
            - registry
            - registry32 (for WOW64)
            - share

    Returns:
        bool: True if successful, raises an error otherwise

    Usage:
        salt.utils.dacl.set_owner('C:\\MyDirectory', 'jsnuffy', 'file')
    '''
    sid = get_sid(principal)

    flags = Flags()

    # Set the user
    try:
        win32security.SetNamedSecurityInfo(
            obj_name,
            flags.type_flags(obj_type),
            flags.element_flags('owner'),
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
                    applies_to='this_folder_subfolders_files',
                    propagate=False):
    '''
    Set the permissions of an object. This can be a file, folder, registry key,
    printer, service, etc...

    Args:

        obj_name (str):
            The object for which to set permissions. This can be the path to a
            file or folder, a registry key, printer, etc. For more information
            about how to format the name see:
            https://msdn.microsoft.com/en-us/library/windows/desktop/aa379593(v=vs.85).aspx

        obj_type (Optional[str]):
            The type of object for which to set permissions. Valid objects are
            as follows:

            - file (default): This is a file or directory
            - service
            - printer
            - registry
            - registry32 (for WOW64)
            - share

        principal (str):
            The name of the user or group for which to set permissions. Can also
            pass a SID.

        permission (str):
            The type of permissions to grant/deny the user. Valid options:

            - full_control
            - modify
            - read_execute
            - read
            -  write

        access_mode(Optional[str]):
            Whether to grant or deny user the access. Valid options are:

            - grant (default): Grants the user access
            - deny: Denies the user access

        reset_perms (Optional[bool]):
            True will overwrite the permissions on the specified object. False
            will append the permissions. Default is False

        protected (Optional[bool]):
            True will disable inheritance for the object. False will enable
            inheritance. None will make no change. Default is None.

        applies_to (Optional[str]):
            The objects to which these permissions will apply. Not all these
            options apply to all object types. Valid options are:

            - this_folder_only: Applies only to this object
            - this_folder_subfolders_files (default): Applies to this object and
              all sub containers and objects
            - this_folder_subfolders: Applies to this object and all sub
              containers.
            - this_folder_files: Applies to this object and all sub-objects,
              minus containers.
            - subfolders_files: Applies to all containers and objects beneath
              this object
            - subfolders_only: Applies to all containers beneath the this object
            - files_only: Applies to all objects beneath this object

        propagate (Optional[bool]):
            Apply these permissions to all sub-containers and objects. Not yet
            implemented. Would only apply to file type objects.

    Returns:
        bool: True if successful, raises an error otherwise

    Usage:
        salt.utils.dacl.set_permissions(
            'C:\\Temp', 'file', 'jsnuffy', 'full_control')
    '''
    sid = get_sid(principal)

    # If you don't pass `obj_name` it will create a blank DACL
    # Otherwise, it will grab the existing DACL and add to it
    if reset_perms:
        dacl = Dacl(obj_type=obj_type)
    else:
        dacl = Dacl(obj_name, obj_type)

    dacl.add_ace(sid, access_mode, applies_to, permission)
    dacl.save(obj_name, obj_type, protected)

    return True


def get_permissions(obj_name):
    dacl = Dacl(obj_name)
    return dacl.get_ace()


