"""
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

.. code-block:: python

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
    *** folder permissions
    list_folder              X
    create_files             X
    create_folders           X
    traverse_folder          X
    delete_subfolders_files  X

    *** file permissions
    read_data                X
    write_data               X
    append_data              X
    execute_file             X

    *** common permissions
    read_ea                  X
    write_ea                 X
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

    .. NOTE::

        'applies to' properties can only be modified on directories. Files
        will always be ``this_folder_only``.

    **Registry types:**

        - this_key_only: Applies only to this key
        - this_key_subkeys: Applies to this key and all subkeys
        - subkeys_only: Applies to all subkeys beneath this object

"""

import logging

import salt.utils.platform
import salt.utils.win_functions
from salt.exceptions import CommandExecutionError, SaltInvocationError

HAS_WIN32 = False
try:
    import pywintypes
    import win32api
    import win32con
    import win32security

    HAS_WIN32 = True
except ImportError:
    pass

log = logging.getLogger(__name__)

__virtualname__ = "dacl"


def __virtual__():
    """
    Only load if Win32 Libraries are installed
    """
    if not salt.utils.platform.is_windows():
        return False, "win_dacl: Requires Windows"

    if not HAS_WIN32:
        return False, "win_dacl: Requires pywin32"

    return __virtualname__


def flags(instantiated=True):
    """
    Helper function for instantiating a Flags object

    Args:

        instantiated (bool):
            True to return an instantiated object, False to return the object
            definition. Use False if inherited by another class. Default is
            True.

    Returns:
        object: An instance of the Flags object or its definition
    """
    if not HAS_WIN32:
        return

    class Flags:
        """
        Object containing all the flags for dealing with Windows permissions
        """

        # Flag Dicts
        ace_perms = {
            "file": {
                "basic": {
                    0x1F01FF: "Full control",
                    0x1301BF: "Modify",
                    0x1201BF: "Read & execute with write",
                    0x1200A9: "Read & execute",
                    0x120089: "Read",
                    0x100116: "Write",
                    "full_control": 0x1F01FF,
                    "modify": 0x1301BF,
                    "read_execute": 0x1200A9,
                    "read": 0x120089,
                    "write": 0x100116,
                },
                "advanced": {
                    # Advanced
                    0x0001: "List folder / read data",
                    0x0002: "Create files / write data",
                    0x0004: "Create folders / append data",
                    0x0008: "Read extended attributes",
                    0x0010: "Write extended attributes",
                    0x0020: "Traverse folder / execute file",
                    0x0040: "Delete subfolders and files",
                    0x0080: "Read attributes",
                    0x0100: "Write attributes",
                    0x10000: "Delete",
                    0x20000: "Read permissions",
                    0x40000: "Change permissions",
                    0x80000: "Take ownership",
                    # 0x100000: 'SYNCHRONIZE',  # This is in all of them
                    # Directory permissions
                    "list_folder": 0x0001,
                    "create_files": 0x0002,
                    "create_folders": 0x0004,
                    "traverse_folder": 0x0020,
                    "delete_subfolders_files": 0x0040,
                    # File permissions
                    "read_data": 0x0001,
                    "write_data": 0x0002,
                    "append_data": 0x0004,
                    "execute_file": 0x0020,
                    # Common permissions
                    "read_ea": 0x0008,
                    "write_ea": 0x0010,
                    "read_attributes": 0x0080,
                    "write_attributes": 0x0100,
                    "delete": 0x10000,
                    "read_permissions": 0x20000,
                    "change_permissions": 0x40000,
                    "take_ownership": 0x80000,
                },
            },
            "registry": {
                "basic": {
                    0xF003F: "Full Control",
                    0x20019: "Read",
                    0x20006: "Write",
                    # Generic Values (These sometimes get hit)
                    0x10000000: "Full Control",
                    0x20000000: "Execute",
                    0x40000000: "Write",
                    0xFFFFFFFF80000000: "Read",
                    "full_control": 0xF003F,
                    "read": 0x20019,
                    "write": 0x20006,
                },
                "advanced": {
                    # Advanced
                    0x0001: "Query Value",
                    0x0002: "Set Value",
                    0x0004: "Create Subkey",
                    0x0008: "Enumerate Subkeys",
                    0x0010: "Notify",
                    0x0020: "Create Link",
                    0x10000: "Delete",
                    0x20000: "Read Control",
                    0x40000: "Write DAC",
                    0x80000: "Write Owner",
                    "query_value": 0x0001,
                    "set_value": 0x0002,
                    "create_subkey": 0x0004,
                    "enum_subkeys": 0x0008,
                    "notify": 0x0010,
                    "create_link": 0x0020,
                    "delete": 0x10000,
                    "read_control": 0x20000,
                    "write_dac": 0x40000,
                    "write_owner": 0x80000,
                },
            },
            "share": {
                "basic": {
                    0x1F01FF: "Full control",
                    0x1301BF: "Change",
                    0x1200A9: "Read",
                    "full_control": 0x1F01FF,
                    "change": 0x1301BF,
                    "read": 0x1200A9,
                },
                "advanced": {},  # No 'advanced' for shares, needed for lookup
            },
            "printer": {
                "basic": {
                    0x20008: "Print",
                    0xF000C: "Manage this printer",
                    0xF0030: "Manage documents",
                    "print": 0x20008,
                    "manage_printer": 0xF000C,
                    "manage_documents": 0xF0030,
                },
                "advanced": {
                    # Advanced
                    0x10004: "Manage this printer",
                    0x0008: "Print",
                    0x20000: "Read permissions",
                    0x40000: "Change permissions",
                    0x80000: "Take ownership",
                    "manage_printer": 0x10004,
                    "print": 0x0008,
                    "read_permissions": 0x20000,
                    "change_permissions": 0x40000,
                    "take_ownership": 0x80000,
                },
            },
            "service": {
                "basic": {
                    0xF01FF: "Full Control",
                    0x2008F: "Read & Write",
                    0x2018D: "Read",
                    0x20002: "Write",
                    "full_control": 0xF01FF,
                    "read_write": 0x2008F,
                    "read": 0x2018D,
                    "write": 0x20002,
                },
                "advanced": {
                    0x0001: "Query Config",
                    0x0002: "Change Config",
                    0x0004: "Query Status",
                    0x0008: "Enumerate Dependents",
                    0x0010: "Start",
                    0x0020: "Stop",
                    0x0040: "Pause/Resume",
                    0x0080: "Interrogate",
                    0x0100: "User-Defined Control",
                    # 0x10000: 'Delete',  # Not visible in the GUI
                    0x20000: "Read Permissions",
                    0x40000: "Change Permissions",
                    0x80000: "Change Owner",
                    "query_config": 0x0001,
                    "change_config": 0x0002,
                    "query_status": 0x0004,
                    "enum_dependents": 0x0008,
                    "start": 0x0010,
                    "stop": 0x0020,
                    "pause_resume": 0x0040,
                    "interrogate": 0x0080,
                    "user_defined": 0x0100,
                    "read_permissions": 0x20000,
                    "change_permissions": 0x40000,
                    "change_owner": 0x80000,
                },
            },
        }

        # These denote inheritance
        # 0x0000 : Not inherited, I don't know the enumeration for this
        # 0x0010 : win32security.INHERITED_ACE

        # All the values in the dict below are combinations of the following
        # enumerations or'ed together
        # 0x0001 : win32security.OBJECT_INHERIT_ACE
        # 0x0002 : win32security.CONTAINER_INHERIT_ACE
        # 0x0004 : win32security.NO_PROPAGATE_INHERIT_ACE
        # 0x0008 : win32security.INHERIT_ONLY_ACE

        # These values only apply to directories. Files will always return
        # "This folder only"
        ace_prop = {
            "file": {
                # for report
                0x0000: "This folder only",
                0x0001: "This folder and files",
                0x0002: "This folder and subfolders",
                0x0003: "This folder, subfolders and files",
                0x0009: "Files only",
                0x000A: "Subfolders only",
                0x000B: "Subfolders and files only",
                # for setting
                "this_folder_only": 0x0000,
                "this_folder_files": 0x0001,
                "this_folder_subfolders": 0x0002,
                "this_folder_subfolders_files": 0x0003,
                "files_only": 0x0009,
                "subfolders_only": 0x000A,
                "subfolders_files": 0x000B,
            },
            "registry": {
                0x0000: "This key only",
                0x0002: "This key and subkeys",
                0x000A: "Subkeys only",
                "this_key_only": 0x0000,
                "this_key_subkeys": 0x0002,
                "subkeys_only": 0x000A,
            },
            "registry32": {
                0x0000: "This key only",
                0x0002: "This key and subkeys",
                0x000A: "Subkeys only",
                "this_key_only": 0x0000,
                "this_key_subkeys": 0x0002,
                "subkeys_only": 0x000A,
            },
        }

        ace_type = {
            "grant": win32security.ACCESS_ALLOWED_ACE_TYPE,
            "deny": win32security.ACCESS_DENIED_ACE_TYPE,
            win32security.ACCESS_ALLOWED_ACE_TYPE: "grant",
            win32security.ACCESS_DENIED_ACE_TYPE: "deny",
        }

        element = {
            "dacl": win32security.DACL_SECURITY_INFORMATION,
            "group": win32security.GROUP_SECURITY_INFORMATION,
            "owner": win32security.OWNER_SECURITY_INFORMATION,
        }

        inheritance = {
            "protected": win32security.PROTECTED_DACL_SECURITY_INFORMATION,
            "unprotected": win32security.UNPROTECTED_DACL_SECURITY_INFORMATION,
        }

        obj_type = {
            "file": win32security.SE_FILE_OBJECT,
            "service": win32security.SE_SERVICE,
            "printer": win32security.SE_PRINTER,
            "registry": win32security.SE_REGISTRY_KEY,
            "registry32": win32security.SE_REGISTRY_WOW64_32KEY,
            "share": win32security.SE_LMSHARE,
        }

    return Flags() if instantiated else Flags


def dacl(obj_name=None, obj_type="file"):
    """
    Helper function for instantiating a Dacl class.

    Args:

        obj_name (str):
            The full path to the object. If None, a blank DACL will be created.
            Default is None.

        obj_type (str):
            The type of object. Default is 'File'

    Returns:
        object: An instantiated Dacl object
    """

    if not HAS_WIN32:
        return

    class Dacl(flags(False)):
        """
        DACL Object
        """

        def __init__(self, obj_name=None, obj_type="file"):
            """
            Either load the DACL from the passed object or create an empty DACL.
            If `obj_name` is not passed, an empty DACL is created.

            Args:

                obj_name (str):
                    The full path to the object. If None, a blank DACL will be
                    created

                obj_type (Optional[str]):
                    The type of object.

            Returns:
                obj: A DACL object

            Usage:

            .. code-block:: python

                # Create an Empty DACL
                dacl = Dacl(obj_type=obj_type)

                # Load the DACL of the named object
                dacl = Dacl(obj_name, obj_type)
            """
            # Validate obj_type
            if obj_type.lower() not in self.obj_type:
                raise SaltInvocationError(
                    'Invalid "obj_type" passed: {}'.format(obj_type)
                )

            self.dacl_type = obj_type.lower()

            if obj_name is None:
                self.dacl = win32security.ACL()
            else:
                if "registry" in self.dacl_type:
                    obj_name = self.get_reg_name(obj_name)

                try:
                    sd = win32security.GetNamedSecurityInfo(
                        obj_name, self.obj_type[self.dacl_type], self.element["dacl"]
                    )
                except pywintypes.error as exc:
                    if "The system cannot find" in exc.strerror:
                        msg = "System cannot find {}".format(obj_name)
                        log.exception(msg)
                        raise CommandExecutionError(msg)
                    raise

                self.dacl = sd.GetSecurityDescriptorDacl()
                if self.dacl is None:
                    self.dacl = win32security.ACL()

        def get_reg_name(self, obj_name):
            """
            Take the obj_name and convert the hive to a valid registry hive.

            Args:

                obj_name (str):
                    The full path to the registry key including the hive, eg:
                    ``HKLM\\SOFTWARE\\salt``. Valid options for the hive are:

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
                str:
                    The full path to the registry key in the format expected by
                    the Windows API

            Usage:

            .. code-block:: python

                import salt.utils.win_dacl
                dacl = salt.utils.win_dacl.Dacl()
                valid_key = dacl.get_reg_name('HKLM\\SOFTWARE\\salt')

                # Returns: MACHINE\\SOFTWARE\\salt
            """
            # Make sure the hive is correct
            # Should be MACHINE, USERS, CURRENT_USER, or CLASSES_ROOT
            hives = {
                # MACHINE
                "HKEY_LOCAL_MACHINE": "MACHINE",
                "MACHINE": "MACHINE",
                "HKLM": "MACHINE",
                # USERS
                "HKEY_USERS": "USERS",
                "USERS": "USERS",
                "HKU": "USERS",
                # CURRENT_USER
                "HKEY_CURRENT_USER": "CURRENT_USER",
                "CURRENT_USER": "CURRENT_USER",
                "HKCU": "CURRENT_USER",
                # CLASSES ROOT
                "HKEY_CLASSES_ROOT": "CLASSES_ROOT",
                "CLASSES_ROOT": "CLASSES_ROOT",
                "HKCR": "CLASSES_ROOT",
            }
            reg = obj_name.split("\\")
            passed_hive = reg.pop(0)

            try:
                valid_hive = hives[passed_hive.upper()]
            except KeyError:
                log.exception("Invalid Registry Hive: %s", passed_hive)
                raise CommandExecutionError(
                    "Invalid Registry Hive: {}".format(passed_hive)
                )

            reg.insert(0, valid_hive)

            return r"\\".join(reg)

        def add_ace(self, principal, access_mode, permissions, applies_to):
            """
            Add an ACE to the DACL

            Args:

                principal (str):
                    The sid of the user/group to for the ACE

                access_mode (str):
                    Determines the type of ACE to add. Must be either ``grant``
                    or ``deny``.

                permissions (str, list):
                    The type of permissions to grant/deny the user. Can be one
                    of the basic permissions, or a list of advanced permissions.

                applies_to (str):
                    The objects to which these permissions will apply. Not all
                    these options apply to all object types.

            Returns:
                bool: True if successful, otherwise False

            Usage:

            .. code-block:: python

                dacl = Dacl(obj_type=obj_type)
                dacl.add_ace(sid, access_mode, permission, applies_to)
                dacl.save(obj_name, protected)
            """
            sid = get_sid(principal)

            if applies_to not in self.ace_prop[self.dacl_type]:
                raise SaltInvocationError(
                    "Invalid 'applies_to' for type {}".format(self.dacl_type)
                )

            if self.dacl is None:
                raise SaltInvocationError("You must load the DACL before adding an ACE")

            # Get the permission flag
            perm_flag = 0
            if isinstance(permissions, str):
                try:
                    perm_flag = self.ace_perms[self.dacl_type]["basic"][permissions]
                except KeyError as exc:
                    msg = "Invalid permission specified: {}".format(permissions)
                    log.exception(msg)
                    raise CommandExecutionError(msg, exc)
            else:
                for perm in permissions:
                    try:
                        perm_flag |= self.ace_perms[self.dacl_type]["advanced"][perm]
                    except KeyError as exc:
                        msg = "Invalid permission specified: {}".format(perm)
                        log.exception(msg)
                        raise CommandExecutionError(msg, exc)

            if access_mode.lower() not in ["grant", "deny"]:
                raise SaltInvocationError("Invalid Access Mode: {}".format(access_mode))

            # Add ACE to the DACL
            # Grant or Deny
            # There's some strange behavior here with the registry when you give
            # grant permissions to the Administrator account... it adds bit 1 to
            # the propagation flag... so 0x2 becomes 0x3 and results in an
            # Unknown propagation in get_permissions. It displays correctly in
            # the GUI, but after you modify in the GUI they change back to 0x2.
            # Other users work correctly
            try:
                if access_mode.lower() == "grant":
                    self.dacl.AddAccessAllowedAceEx(
                        win32security.ACL_REVISION_DS,
                        # Some types don't support propagation
                        # May need to use 0x0000 instead of None
                        self.ace_prop.get(self.dacl_type, {}).get(applies_to),
                        perm_flag,
                        sid,
                    )
                elif access_mode.lower() == "deny":
                    self.dacl.AddAccessDeniedAceEx(
                        win32security.ACL_REVISION_DS,
                        self.ace_prop.get(self.dacl_type, {}).get(applies_to),
                        perm_flag,
                        sid,
                    )
                else:
                    log.exception("Invalid access mode: %s", access_mode)
                    raise SaltInvocationError(
                        "Invalid access mode: {}".format(access_mode)
                    )
            except Exception as exc:  # pylint: disable=broad-except
                return False, "Error: {}".format(exc)

            return True

        def order_acl(self):
            """
            Put the ACEs in the ACL in the proper order. This is necessary
            because the add_ace function puts ACEs at the end of the list
            without regard for order. This will cause the following Windows
            Security dialog to appear when viewing the security for the object:

            ``The permissions on Directory are incorrectly ordered, which may
            cause some entries to be ineffective.``

            .. note:: Run this function after adding all your ACEs.

            Proper Orders is as follows:

                1. Implicit Deny
                2. Inherited Deny
                3. Implicit Deny Object
                4. Inherited Deny Object
                5. Implicit Allow
                6. Inherited Allow
                7. Implicit Allow Object
                8. Inherited Allow Object

            Usage:

            .. code-block:: python

                dacl = Dacl(obj_type=obj_type)
                dacl.add_ace(sid, access_mode, applies_to, permission)
                dacl.order_acl()
                dacl.save(obj_name, protected)
            """
            new_dacl = Dacl()
            deny_dacl = Dacl()
            deny_obj_dacl = Dacl()
            allow_dacl = Dacl()
            allow_obj_dacl = Dacl()

            # Load Non-Inherited ACEs first
            for i in range(0, self.dacl.GetAceCount()):
                ace = self.dacl.GetAce(i)
                if ace[0][1] & win32security.INHERITED_ACE == 0:
                    if ace[0][0] == win32security.ACCESS_DENIED_ACE_TYPE:
                        deny_dacl.dacl.AddAccessDeniedAceEx(
                            win32security.ACL_REVISION_DS, ace[0][1], ace[1], ace[2]
                        )
                    elif ace[0][0] == win32security.ACCESS_DENIED_OBJECT_ACE_TYPE:
                        deny_obj_dacl.dacl.AddAccessDeniedAceEx(
                            win32security.ACL_REVISION_DS, ace[0][1], ace[1], ace[2]
                        )
                    elif ace[0][0] == win32security.ACCESS_ALLOWED_ACE_TYPE:
                        allow_dacl.dacl.AddAccessAllowedAceEx(
                            win32security.ACL_REVISION_DS, ace[0][1], ace[1], ace[2]
                        )
                    elif ace[0][0] == win32security.ACCESS_ALLOWED_OBJECT_ACE_TYPE:
                        allow_obj_dacl.dacl.AddAccessAllowedAceEx(
                            win32security.ACL_REVISION_DS, ace[0][1], ace[1], ace[2]
                        )

            # Load Inherited ACEs last
            for i in range(0, self.dacl.GetAceCount()):
                ace = self.dacl.GetAce(i)
                if (
                    ace[0][1] & win32security.INHERITED_ACE
                    == win32security.INHERITED_ACE
                ):
                    ace_prop = ace[0][1] ^ win32security.INHERITED_ACE
                    if ace[0][0] == win32security.ACCESS_DENIED_ACE_TYPE:
                        deny_dacl.dacl.AddAccessDeniedAceEx(
                            win32security.ACL_REVISION_DS, ace_prop, ace[1], ace[2]
                        )
                    elif ace[0][0] == win32security.ACCESS_DENIED_OBJECT_ACE_TYPE:
                        deny_obj_dacl.dacl.AddAccessDeniedAceEx(
                            win32security.ACL_REVISION_DS, ace_prop, ace[1], ace[2]
                        )
                    elif ace[0][0] == win32security.ACCESS_ALLOWED_ACE_TYPE:
                        allow_dacl.dacl.AddAccessAllowedAceEx(
                            win32security.ACL_REVISION_DS, ace_prop, ace[1], ace[2]
                        )
                    elif ace[0][0] == win32security.ACCESS_ALLOWED_OBJECT_ACE_TYPE:
                        allow_obj_dacl.dacl.AddAccessAllowedAceEx(
                            win32security.ACL_REVISION_DS, ace_prop, ace[1], ace[2]
                        )

            # Combine ACEs in the proper order
            # Deny, Deny Object, Allow, Allow Object
            # Deny
            for i in range(0, deny_dacl.dacl.GetAceCount()):
                ace = deny_dacl.dacl.GetAce(i)
                new_dacl.dacl.AddAccessDeniedAceEx(
                    win32security.ACL_REVISION_DS, ace[0][1], ace[1], ace[2]
                )

            # Deny Object
            for i in range(0, deny_obj_dacl.dacl.GetAceCount()):
                ace = deny_obj_dacl.dacl.GetAce(i)
                new_dacl.dacl.AddAccessDeniedAceEx(
                    win32security.ACL_REVISION_DS,
                    ace[0][1] ^ win32security.INHERITED_ACE,
                    ace[1],
                    ace[2],
                )

            # Allow
            for i in range(0, allow_dacl.dacl.GetAceCount()):
                ace = allow_dacl.dacl.GetAce(i)
                new_dacl.dacl.AddAccessAllowedAceEx(
                    win32security.ACL_REVISION_DS, ace[0][1], ace[1], ace[2]
                )

            # Allow Object
            for i in range(0, allow_obj_dacl.dacl.GetAceCount()):
                ace = allow_obj_dacl.dacl.GetAce(i)
                new_dacl.dacl.AddAccessAllowedAceEx(
                    win32security.ACL_REVISION_DS,
                    ace[0][1] ^ win32security.INHERITED_ACE,
                    ace[1],
                    ace[2],
                )

            # Set the new dacl
            self.dacl = new_dacl.dacl

        def get_ace(self, principal):
            """
            Get the ACE for a specific principal.

            Args:

                principal (str):
                    The name of the user or group for which to get the ace. Can
                    also be a SID.

            Returns:
                dict: A dictionary containing the ACEs found for the principal

            Usage:

            .. code-block:: python

                dacl = Dacl(obj_type=obj_type)
                dacl.get_ace()
            """
            principal = get_name(principal)
            aces = self.list_aces()

            # Filter for the principal
            ret = {}
            for inheritance in aces:
                if principal in aces[inheritance]:
                    ret[inheritance] = {principal: aces[inheritance][principal]}

            return ret

        def list_aces(self):
            """
            List all Entries in the dacl.

            Returns:
                dict: A dictionary containing the ACEs for the object

            Usage:

            .. code-block:: python

                dacl = Dacl('C:\\Temp')
                dacl.list_aces()
            """
            ret = {"Inherited": {}, "Not Inherited": {}}

            # loop through each ACE in the DACL
            for i in range(0, self.dacl.GetAceCount()):
                ace = self.dacl.GetAce(i)

                # Get ACE Elements
                user, a_type, a_prop, a_perms, inheritance = self._ace_to_dict(ace)

                if user in ret[inheritance]:
                    ret[inheritance][user][a_type] = {
                        "applies to": a_prop,
                        "permissions": a_perms,
                    }
                else:
                    ret[inheritance][user] = {
                        a_type: {"applies to": a_prop, "permissions": a_perms}
                    }

            return ret

        def _ace_to_dict(self, ace):
            """
            Helper function for creating the ACE return dictionary
            """
            # Get the principal from the sid (object sid)
            sid = win32security.ConvertSidToStringSid(ace[2])
            try:
                principal = get_name(sid)
            except CommandExecutionError:
                principal = sid

            # Get the ace type
            ace_type = self.ace_type[ace[0][0]]

            # Is the inherited ace flag present
            inherited = ace[0][1] & win32security.INHERITED_ACE == 16

            # If "Only apply these permissions to objects and/or containers
            # within this container" is checked, there is a 0x4 flag set
            container_only = ace[0][1] & win32security.NO_PROPAGATE_INHERIT_ACE == 4

            # Ace Propagation
            ace_prop = "NA"

            # Get the ace propagation properties
            if self.dacl_type in ["file", "registry", "registry32"]:

                ace_prop = ace[0][1]

                # Remove the inherited ace flag and get propagation
                if inherited:
                    ace_prop = ace[0][1] ^ win32security.INHERITED_ACE

                if container_only:
                    ace_prop = ace[0][1] ^ win32security.NO_PROPAGATE_INHERIT_ACE

                # Lookup the propagation
                try:
                    ace_prop = self.ace_prop[self.dacl_type][ace_prop]
                except KeyError:
                    ace_prop = "Unknown propagation"

            # Get the object type
            obj_type = "registry" if self.dacl_type == "registry32" else self.dacl_type

            # Get the ace permissions
            # Check basic permissions first
            ace_perms = self.ace_perms[obj_type]["basic"].get(ace[1], [])

            # If it didn't find basic perms, check advanced permissions
            if not ace_perms:
                ace_perms = []
                for perm in self.ace_perms[obj_type]["advanced"]:
                    # Don't match against the string perms
                    if isinstance(perm, str):
                        continue
                    if ace[1] & perm == perm:
                        ace_perms.append(self.ace_perms[obj_type]["advanced"][perm])
                ace_perms.sort()

            # If still nothing, it must be undefined
            if not ace_perms:
                ace_perms = ["Undefined Permission: {}".format(ace[1])]

            return (
                principal,
                ace_type,
                ace_prop,
                ace_perms,
                "Inherited" if inherited else "Not Inherited",
            )

        def rm_ace(self, principal, ace_type="all"):
            """
            Remove a specific ACE from the DACL.

            Args:

                principal (str):
                    The user whose ACE to remove. Can be the user name or a SID.

                ace_type (str):
                    The type of ACE to remove. If not specified, all ACEs will
                    be removed. Default is 'all'. Valid options are:

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
            """
            sid = get_sid(principal)
            ace_type = ace_type.lower()
            offset = 0
            ret = []

            for i in range(0, self.dacl.GetAceCount()):
                ace = self.dacl.GetAce(i - offset)

                # Is the inherited ace flag present
                inherited = ace[0][1] & win32security.INHERITED_ACE == 16

                if ace[2] == sid and not inherited:
                    if ace_type == "all" or self.ace_type[ace[0][0]] == ace_type:
                        self.dacl.DeleteAce(i - offset)
                        ret.append(self._ace_to_dict(ace))
                        offset += 1

            if not ret:
                ret = ["ACE not found for {}".format(principal)]

            return ret

        def rm_all_aces(self, ace_type="all"):
            """
            Removes all ACEs from the DACL.

            Args:

                ace_type (str):
                    The type of ACE to remove. If not specified, all ACEs will
                    be removed. Default is 'all'. Valid options are:

                    - 'grant'
                    - 'deny'
                    - 'all'

            Returns:
                list: List of removed aces

            Usage:

            .. code-block:: python

                dacl = Dacl(obj_name='C:\\temp', obj_type='file')
                dacl.rm_all_aces()
                dacl.save(obj_name='C:\\temp')
            """
            offset = 0
            ret = []

            ace_type = ace_type.lower()

            for i in range(0, self.dacl.GetAceCount()):
                ace = self.dacl.GetAce(i - offset)

                # Is the inherited ace flag present
                inherited = ace[0][1] & win32security.INHERITED_ACE == 16

                if not inherited:
                    if ace_type == "all" or self.ace_type[ace[0][0]] == ace_type:
                        self.dacl.DeleteAce(i - offset)
                        ret.append(self._ace_to_dict(ace))
                        offset += 1

            return ret

        def save(self, obj_name, protected=None):
            """
            Save the DACL

            Args:

                obj_name (str):
                    The object for which to set permissions. This can be the
                    path to a file or folder, a registry key, printer, etc. For
                    more information about how to format the name see:

                    https://msdn.microsoft.com/en-us/library/windows/desktop/aa379593(v=vs.85).aspx

                protected (Optional[bool]):
                    True will disable inheritance for the object. False will
                    enable inheritance. None will make no change. Default is
                    ``None``.

            Returns:
                bool: True if successful, Otherwise raises an exception

            Usage:

            .. code-block:: python

                dacl = Dacl(obj_type='file')
                dacl.save('C:\\Temp', True)
            """
            sec_info = self.element["dacl"]

            if protected is not None:
                if protected:
                    sec_info = sec_info | self.inheritance["protected"]
                else:
                    sec_info = sec_info | self.inheritance["unprotected"]

            if self.dacl_type in ["registry", "registry32"]:
                obj_name = self.get_reg_name(obj_name)

            try:
                win32security.SetNamedSecurityInfo(
                    obj_name,
                    self.obj_type[self.dacl_type],
                    sec_info,
                    None,
                    None,
                    self.dacl,
                    None,
                )
            except pywintypes.error as exc:
                raise CommandExecutionError(
                    "Failed to set permissions: {}".format(obj_name), exc.strerror
                )

            return True

    return Dacl(obj_name, obj_type)


def get_sid(principal):
    """
    Converts a username to a sid, or verifies a sid. Required for working with
    the DACL.

    Args:

        principal(str):
            The principal to lookup the sid. Can be a sid or a username.

    Returns:
        PySID Object: A sid

    Usage:

    .. code-block:: python

        # Get a user's sid
        salt.utils.win_dacl.get_sid('jsnuffy')

        # Verify that the sid is valid
        salt.utils.win_dacl.get_sid('S-1-5-32-544')
    """
    # If None is passed, use the Universal Well-known SID "Null SID"
    if principal is None:
        principal = "NULL SID"

    # Test if the user passed a sid or a name
    try:
        sid = salt.utils.win_functions.get_sid_from_name(principal)
    except CommandExecutionError:
        sid = principal

    # Test if the SID is valid
    try:
        sid = win32security.ConvertStringSidToSid(sid)
    except pywintypes.error:
        log.exception("Invalid user/group or sid: %s", principal)
        raise CommandExecutionError("Invalid user/group or sid: {}".format(principal))
    except TypeError:
        raise CommandExecutionError

    return sid


def get_sid_string(principal):
    """
    Converts a PySID object to a string SID.

    Args:

        principal(str):
            The principal to lookup the sid. Must be a PySID object.

    Returns:
        str: A string sid

    Usage:

    .. code-block:: python

        # Get a PySID object
        py_sid = salt.utils.win_dacl.get_sid('jsnuffy')

        # Get the string version of the SID
        salt.utils.win_dacl.get_sid_string(py_sid)
    """
    # If None is passed, use the Universal Well-known SID "Null SID"
    if principal is None:
        principal = "NULL SID"

    try:
        return win32security.ConvertSidToStringSid(principal)
    except TypeError:
        # Not a PySID object
        principal = get_sid(principal)

    try:
        return win32security.ConvertSidToStringSid(principal)
    except pywintypes.error:
        log.exception("Invalid principal %s", principal)
        raise CommandExecutionError("Invalid principal {}".format(principal))


def get_name(principal):
    """
    Gets the name from the specified principal.

    Args:

        principal (str):
            Find the Normalized name based on this. Can be a PySID object, a SID
            string, or a user name in any capitalization.

            .. note::
                Searching based on the user name can be slow on hosts connected
                to large Active Directory domains.

    Returns:
        str: The name that corresponds to the passed principal

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.get_name('S-1-5-32-544')
        salt.utils.win_dacl.get_name('adminisTrators')
    """
    # If this is a PySID object, use it
    if isinstance(principal, pywintypes.SIDType):
        sid_obj = principal
    else:
        # If None is passed, use the Universal Well-known SID for "Null SID"
        if principal is None:
            principal = "S-1-0-0"
        # Try Converting String SID to SID Object first as it's least expensive
        try:
            sid_obj = win32security.ConvertStringSidToSid(principal)
        except pywintypes.error:
            # Try Getting the SID Object by Name Lookup last
            # This is expensive, especially on large AD Domains
            try:
                sid_obj = win32security.LookupAccountName(None, principal)[0]
            except pywintypes.error:
                # This is not a PySID object, a SID String, or a valid Account
                # Name. Just pass it and let the LookupAccountSid function try
                # to resolve it
                sid_obj = principal

    # By now we should have a valid PySID object
    str_sid = get_sid_string(sid_obj)

    try:
        name = win32security.LookupAccountSid(None, sid_obj)[0]

        # Let's Check for Virtual Service Accounts
        # Virtual Accounts must be prepended with NT Service in order to resolve
        # properly
        # https://docs.microsoft.com/en-us/previous-versions/technet-magazine/cc138011(v=msdn.10)
        # https://docs.microsoft.com/en-us/previous-versions/windows/it-pro/windows-server-2008-R2-and-2008/dd548356(v=ws.10)
        if str_sid.startswith("S-1-5-80"):
            name = "NT Service\\{}".format(name)

        return name
    except (pywintypes.error, TypeError) as exc:
        # Microsoft introduced the concept of Capability SIDs in Windows 8
        # https://docs.microsoft.com/en-us/windows/security/identity-protection/access-control/security-identifiers#capability-sids
        # https://support.microsoft.com/en-us/help/4502539/some-sids-do-not-resolve-into-friendly-names
        # https://support.microsoft.com/en-us/help/243330/well-known-security-identifiers-in-windows-operating-systems
        # These types of SIDs do not resolve, so we'll just ignore them for this
        # All capability SIDs begin with `S-1-15-3`, so we'll only throw an
        # error when the sid does not begin with `S-1-15-3`
        if not str_sid.startswith("S-1-15-3"):
            message = 'Error resolving "{}"'.format(principal)
            if type(exc) == pywintypes.error:
                win_error = win32api.FormatMessage(exc.winerror).rstrip("\n")
                message = "{}: {}".format(message, win_error)
            log.exception(message)
            raise CommandExecutionError(message, exc)


def get_owner(obj_name, obj_type="file"):
    r"""
    Gets the owner of the passed object

    Args:

        obj_name (str):
            The path for which to obtain owner information. The format of this
            parameter is different depending on the ``obj_type``

        obj_type (str):
            The type of object to query. This value changes the format of the
            ``obj_name`` parameter as follows:

            - file: indicates a file or directory
                - a relative path, such as ``FileName.txt`` or ``..\FileName``
                - an absolute path, such as ``C:\DirName\FileName.txt``
                - A UNC name, such as ``\\ServerName\ShareName\FileName.txt``
            - service: indicates the name of a Windows service
            - printer: indicates the name of a printer
            - registry: indicates a registry key
                - Uses the following literal strings to denote the hive:
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
                - Should be in the format of ``HIVE\Path\To\Key``. For example,
                    ``HKLM\SOFTWARE\Windows``
            - registry32: indicates a registry key under WOW64. Formatting is
                the same as it is for ``registry``
            - share: indicates a network share

    Returns:
        str: The owner (group or user)

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.get_owner('c:\\file')
    """
    # Not all filesystems mountable within windows have SecurityDescriptors.
    # For instance, some mounted SAMBA shares, or VirtualBox shared folders. If
    # we can't load a file descriptor for the file, we default to "None"
    # http://support.microsoft.com/kb/243330

    try:
        obj_type_flag = flags().obj_type[obj_type.lower()]
    except KeyError:
        raise SaltInvocationError('Invalid "obj_type" passed: {}'.format(obj_type))

    if obj_type in ["registry", "registry32"]:
        obj_name = dacl().get_reg_name(obj_name)

    try:
        security_descriptor = win32security.GetNamedSecurityInfo(
            obj_name, obj_type_flag, win32security.OWNER_SECURITY_INFORMATION
        )
        owner_sid = security_descriptor.GetSecurityDescriptorOwner()

    except MemoryError:
        # Generic Memory Error (Windows Server 2003+)
        owner_sid = "S-1-0-0"

    except pywintypes.error as exc:
        # Incorrect function error (Windows Server 2008+)
        if exc.winerror == 1 or exc.winerror == 50:
            owner_sid = "S-1-0-0"
        else:
            log.exception("Failed to get the owner: %s", obj_name)
            raise CommandExecutionError(
                "Failed to get owner: {}".format(obj_name), exc.strerror
            )

    return get_name(owner_sid)


def get_primary_group(obj_name, obj_type="file"):
    r"""
    Gets the primary group of the passed object

    Args:

        obj_name (str):
            The path for which to obtain primary group information

        obj_type (str):
            The type of object to query. This value changes the format of the
            ``obj_name`` parameter as follows:

            - file: indicates a file or directory
                - a relative path, such as ``FileName.txt`` or ``..\FileName``
                - an absolute path, such as ``C:\DirName\FileName.txt``
                - A UNC name, such as ``\\ServerName\ShareName\FileName.txt``
            - service: indicates the name of a Windows service
            - printer: indicates the name of a printer
            - registry: indicates a registry key
                - Uses the following literal strings to denote the hive:
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
                - Should be in the format of ``HIVE\Path\To\Key``. For example,
                    ``HKLM\SOFTWARE\Windows``
            - registry32: indicates a registry key under WOW64. Formatting is
                the same as it is for ``registry``
            - share: indicates a network share

    Returns:
        str: The primary group for the object

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.get_primary_group('c:\\file')
    """
    # Not all filesystems mountable within windows have SecurityDescriptors.
    # For instance, some mounted SAMBA shares, or VirtualBox shared folders. If
    # we can't load a file descriptor for the file, we default to "Everyone"
    # http://support.microsoft.com/kb/243330

    # Validate obj_type
    try:
        obj_type_flag = flags().obj_type[obj_type.lower()]
    except KeyError:
        raise SaltInvocationError('Invalid "obj_type" passed: {}'.format(obj_type))

    if "registry" in obj_type.lower():
        obj_name = dacl().get_reg_name(obj_name)
        log.debug("Name converted to: %s", obj_name)

    try:
        security_descriptor = win32security.GetNamedSecurityInfo(
            obj_name, obj_type_flag, win32security.GROUP_SECURITY_INFORMATION
        )
        primary_group_gid = security_descriptor.GetSecurityDescriptorGroup()

    except MemoryError:
        # Generic Memory Error (Windows Server 2003+)
        primary_group_gid = "S-1-0-0"

    except pywintypes.error as exc:
        # Incorrect function error (Windows Server 2008+)
        if exc.winerror == 1 or exc.winerror == 50:
            primary_group_gid = "S-1-0-0"
        else:
            log.exception("Failed to get the primary group: %s", obj_name)
            raise CommandExecutionError(
                "Failed to get primary group: {}".format(obj_name), exc.strerror
            )

    return get_name(win32security.ConvertSidToStringSid(primary_group_gid))


def set_owner(obj_name, principal, obj_type="file"):
    """
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
            The type of object for which to set the owner. Default is ``file``

    Returns:
        bool: True if successful, raises an error otherwise

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.set_owner('C:\\MyDirectory', 'jsnuffy', 'file')
    """
    sid = get_sid(principal)

    obj_flags = flags()

    # Validate obj_type
    if obj_type.lower() not in obj_flags.obj_type:
        raise SaltInvocationError('Invalid "obj_type" passed: {}'.format(obj_type))

    if "registry" in obj_type.lower():
        obj_name = dacl().get_reg_name(obj_name)

    # To set the owner to something other than the logged in user requires
    # SE_TAKE_OWNERSHIP_NAME and SE_RESTORE_NAME privileges
    # Enable them for the logged in user
    # Setup the privilege set
    new_privs = set()
    luid = win32security.LookupPrivilegeValue("", "SeTakeOwnershipPrivilege")
    new_privs.add((luid, win32con.SE_PRIVILEGE_ENABLED))
    luid = win32security.LookupPrivilegeValue("", "SeRestorePrivilege")
    new_privs.add((luid, win32con.SE_PRIVILEGE_ENABLED))

    # Get the current token
    p_handle = win32api.GetCurrentProcess()
    t_handle = win32security.OpenProcessToken(
        p_handle, win32security.TOKEN_ALL_ACCESS | win32con.TOKEN_ADJUST_PRIVILEGES
    )

    # Enable the privileges
    win32security.AdjustTokenPrivileges(t_handle, 0, new_privs)

    # Set the user
    try:
        win32security.SetNamedSecurityInfo(
            obj_name,
            obj_flags.obj_type[obj_type.lower()],
            obj_flags.element["owner"],
            sid,
            None,
            None,
            None,
        )
    except pywintypes.error as exc:
        log.exception("Failed to make %s the owner: %s", principal, exc)
        raise CommandExecutionError(
            "Failed to set owner: {}".format(obj_name), exc.strerror
        )

    return True


def set_primary_group(obj_name, principal, obj_type="file"):
    """
    Set the primary group of an object. This can be a file, folder, registry
    key, printer, service, etc...

    Args:

        obj_name (str):
            The object for which to set primary group. This can be the path to a
            file or folder, a registry key, printer, etc. For more information
            about how to format the name see:

            https://msdn.microsoft.com/en-us/library/windows/desktop/aa379593(v=vs.85).aspx

        principal (str):
            The name of the group to make primary for the object. Can also pass
            a SID.

        obj_type (Optional[str]):
            The type of object for which to set the primary group.

    Returns:
        bool: True if successful, raises an error otherwise

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.set_primary_group('C:\\MyDirectory', 'Administrators', 'file')
    """
    # Windows has the concept of a group called 'None'. It is the default group
    # for all Objects. If the user passes None, assume 'None'
    if principal is None:
        principal = "None"

    gid = get_sid(principal)

    obj_flags = flags()

    # Validate obj_type
    if obj_type.lower() not in obj_flags.obj_type:
        raise SaltInvocationError('Invalid "obj_type" passed: {}'.format(obj_type))

    if "registry" in obj_type.lower():
        obj_name = dacl().get_reg_name(obj_name)

    # To set the owner to something other than the logged in user requires
    # SE_TAKE_OWNERSHIP_NAME and SE_RESTORE_NAME privileges
    # Enable them for the logged in user
    # Setup the privilege set
    new_privs = set()
    luid = win32security.LookupPrivilegeValue("", "SeTakeOwnershipPrivilege")
    new_privs.add((luid, win32con.SE_PRIVILEGE_ENABLED))
    luid = win32security.LookupPrivilegeValue("", "SeRestorePrivilege")
    new_privs.add((luid, win32con.SE_PRIVILEGE_ENABLED))

    # Get the current token
    p_handle = win32api.GetCurrentProcess()
    t_handle = win32security.OpenProcessToken(
        p_handle, win32security.TOKEN_ALL_ACCESS | win32con.TOKEN_ADJUST_PRIVILEGES
    )

    # Enable the privileges
    win32security.AdjustTokenPrivileges(t_handle, 0, new_privs)

    # Set the user
    try:
        win32security.SetNamedSecurityInfo(
            obj_name,
            obj_flags.obj_type[obj_type.lower()],
            obj_flags.element["group"],
            None,
            gid,
            None,
            None,
        )
    except pywintypes.error as exc:
        log.exception("Failed to make %s the primary group: %s", principal, exc)
        raise CommandExecutionError(
            "Failed to set primary group: {}".format(obj_name), exc.strerror
        )

    return True


def set_permissions(
    obj_name,
    principal,
    permissions,
    access_mode="grant",
    applies_to=None,
    obj_type="file",
    reset_perms=False,
    protected=None,
):
    """
    Set the permissions of an object. This can be a file, folder, registry key,
    printer, service, etc...

    Args:

        obj_name (str):
            The object for which to set permissions. This can be the path to a
            file or folder, a registry key, printer, etc. For more information
            about how to format the name see:

            https://msdn.microsoft.com/en-us/library/windows/desktop/aa379593(v=vs.85).aspx

        principal (str):
            The name of the user or group for which to set permissions. Can also
            pass a SID.

        permissions (str, list):
            The type of permissions to grant/deny the user. Can be one of the
            basic permissions, or a list of advanced permissions.

        access_mode (Optional[str]):
            Whether to grant or deny user the access. Valid options are:

            - grant (default): Grants the user access
            - deny: Denies the user access

        applies_to (Optional[str]):
            The objects to which these permissions will apply. Not all these
            options apply to all object types. Defaults to
            'this_folder_subfolders_files'

        obj_type (Optional[str]):
            The type of object for which to set permissions. Default is 'file'

        reset_perms (Optional[bool]):
            True will overwrite the permissions on the specified object. False
            will append the permissions. Default is False

        protected (Optional[bool]):
            True will disable inheritance for the object. False will enable
            inheritance. None will make no change. Default is None.

    Returns:
        bool: True if successful, raises an error otherwise

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.set_permissions(
            'C:\\Temp', 'jsnuffy', 'full_control', 'grant')
    """
    # Set up applies_to defaults used by registry and file types
    if applies_to is None:
        if "registry" in obj_type.lower():
            applies_to = "this_key_subkeys"
        elif obj_type.lower() == "file":
            applies_to = "this_folder_subfolders_files"

    # If reset_perms is true, it will create a blank DACL
    # Otherwise, it will grab the existing DACL and add to it
    if reset_perms:
        obj_dacl = dacl(obj_type=obj_type)
    else:
        obj_dacl = dacl(obj_name, obj_type)
        obj_dacl.rm_ace(principal, access_mode)

    obj_dacl.add_ace(principal, access_mode, permissions, applies_to)

    obj_dacl.order_acl()

    obj_dacl.save(obj_name, protected)

    return True


def rm_permissions(obj_name, principal, ace_type="all", obj_type="file"):
    r"""
    Remove a user's ACE from an object. This can be a file, folder, registry
    key, printer, service, etc...

    Args:

        obj_name (str):
            The object from which to remove the ace. This can be the
            path to a file or folder, a registry key, printer, etc. For more
            information about how to format the name see:

            https://msdn.microsoft.com/en-us/library/windows/desktop/aa379593(v=vs.85).aspx

        principal (str):
            The name of the user or group for which to set permissions. Can also
            pass a SID.

        ace_type (Optional[str]):
            The type of ace to remove. There are two types of ACEs, 'grant' and
            'deny'. 'all' will remove all ACEs for the user. Default is 'all'

        obj_type (Optional[str]):
            The type of object for which to set permissions. Default is 'file'

    Returns:
        bool: True if successful, raises an error otherwise

    Usage:

    .. code-block:: python

        # Remove jsnuffy's grant ACE from C:\Temp
        salt.utils.win_dacl.rm_permissions('C:\\Temp', 'jsnuffy', 'grant')

        # Remove all ACEs for jsnuffy from C:\Temp
        salt.utils.win_dacl.rm_permissions('C:\\Temp', 'jsnuffy')
    """
    obj_dacl = dacl(obj_name, obj_type)

    obj_dacl.rm_ace(principal, ace_type)
    obj_dacl.save(obj_name)

    return True


def get_permissions(obj_name, principal=None, obj_type="file"):
    """
    Get the permissions for the passed object

    Args:

        obj_name (str):
            The name of or path to the object.

        principal (Optional[str]):
            The name of the user or group for which to get permissions. Can also
            pass a SID. If None, all ACEs defined on the object will be
            returned. Default is None

        obj_type (Optional[str]):
            The type of object for which to get permissions.

    Returns:
        dict: A dictionary representing the object permissions

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.get_permissions('C:\\Temp')
    """
    obj_dacl = dacl(obj_name=obj_name, obj_type=obj_type)

    if principal is None:
        return obj_dacl.list_aces()

    return obj_dacl.get_ace(principal)


def has_permission(
    obj_name, principal, permission, access_mode="grant", obj_type="file", exact=True
):
    r"""
    Check if the object has a specific permission

    Args:

        obj_name (str):
            The name of or path to the object.

        principal (str):
            The name of the user or group for which to get permissions. Can also
            pass a SID.

        permission (str):
            The permission to verify. Valid options depend on the obj_type.

        access_mode (Optional[str]):
            The access mode to check. Is the user granted or denied the
            permission. Default is 'grant'. Valid options are:

            - grant
            - deny

        obj_type (Optional[str]):
            The type of object for which to check permissions. Default is 'file'

        exact (Optional[bool]):
            True for an exact match, otherwise check to see if the permission is
            included in the ACE. Default is True

    Returns:
        bool: True if the object has the permission, otherwise False

    Usage:

    .. code-block:: python

        # Does Joe have read permissions to C:\Temp
        salt.utils.win_dacl.has_permission('C:\\Temp', 'joe', 'read', 'grant', exact=False)

        # Does Joe have Full Control of C:\Temp
        salt.utils.win_dacl.has_permission('C:\\Temp', 'joe', 'full_control', 'grant')
    """
    # Validate access_mode
    if access_mode.lower() not in ["grant", "deny"]:
        raise SaltInvocationError(
            'Invalid "access_mode" passed: {}'.format(access_mode)
        )
    access_mode = access_mode.lower()

    # Get the DACL
    obj_dacl = dacl(obj_name, obj_type)

    obj_type = obj_type.lower()

    # Get a PySID object
    sid = get_sid(principal)

    # Get the passed permission flag, check basic first
    chk_flag = obj_dacl.ace_perms[obj_type]["basic"].get(
        permission.lower(),
        obj_dacl.ace_perms[obj_type]["advanced"].get(permission.lower(), False),
    )
    if not chk_flag:
        raise SaltInvocationError('Invalid "permission" passed: {}'.format(permission))

    # Check each ace for sid and type
    cur_flag = None
    for i in range(0, obj_dacl.dacl.GetAceCount()):
        ace = obj_dacl.dacl.GetAce(i)
        if ace[2] == sid and obj_dacl.ace_type[ace[0][0]] == access_mode:
            cur_flag = ace[1]

    # If the ace is empty, return false
    if not cur_flag:
        return False

    # Check if the ACE contains the exact flag
    if exact:
        return cur_flag == chk_flag

    # Check if the ACE contains the permission
    return cur_flag & chk_flag == chk_flag


def has_permissions(
    obj_name, principal, permissions, access_mode="grant", obj_type="file", exact=True
):
    r"""
    Check if the object has the passed permissions. Can be all them or the exact
    permissions passed and nothing more.

    Args:

        obj_name (str):
            The name of or path to the object.

        principal (str):
            The name of the user or group for which to get permissions. Can also
            pass a SID.

        permissions (list):
            The list of permissions to verify

        access_mode (Optional[str]):
            The access mode to check. Is the user granted or denied the
            permission. Default is 'grant'. Valid options are:

            - grant
            - deny

        obj_type (Optional[str]):
            The type of object for which to check permissions. Default is 'file'

        exact (Optional[bool]):
            ``True`` checks if the permissions are exactly those passed in
            permissions. ``False`` checks to see if the permissions are included
            in the ACE. Default is ``True``

    Returns:
        bool: True if the object has the permission, otherwise False

    Usage:

    .. code-block:: python

        # Does Joe have read and write permissions to C:\Temp
        salt.utils.win_dacl.has_permission('C:\\Temp', 'joe', ['read', 'write'], 'grant', exact=False)

        # Does Joe have Full Control of C:\Temp
        salt.utils.win_dacl.has_permissions('C:\\Temp', 'joe', 'full_control', 'grant')
    """
    # If this is a single permission, use has_permission function
    if isinstance(permissions, str):
        return has_permission(
            obj_name=obj_name,
            obj_type=obj_type,
            permission=permissions,
            access_mode=access_mode,
            principal=principal,
            exact=exact,
        )

    # Validate access_mode
    if access_mode.lower() not in ["grant", "deny"]:
        raise SaltInvocationError(
            'Invalid "access_mode" passed: {}'.format(access_mode)
        )
    access_mode = access_mode.lower()

    # Get the DACL
    obj_dacl = dacl(obj_name, obj_type)

    obj_type = obj_type.lower()

    # Get a PySID object
    sid = get_sid(principal)

    # Get the passed permission flag, check basic first
    chk_flag = 0x0
    for permission in permissions:
        chk_flag |= obj_dacl.ace_perms[obj_type]["basic"].get(
            permission.lower(),
            obj_dacl.ace_perms[obj_type]["advanced"].get(permission.lower(), False),
        )
        if not chk_flag:
            raise SaltInvocationError(
                'Invalid "permission" passed: {}'.format(permission)
            )

    # Check each ace for sid and type
    cur_flag = None
    for i in range(0, obj_dacl.dacl.GetAceCount()):
        ace = obj_dacl.dacl.GetAce(i)
        if ace[2] == sid and obj_dacl.ace_type[ace[0][0]] == access_mode:
            cur_flag = ace[1]

    # If the ace is empty, return false
    if not cur_flag:
        return False

    # Check if the ACE contains the exact flag
    if exact:
        return cur_flag == chk_flag

    # Check if the ACE contains the permission
    return cur_flag & chk_flag == chk_flag


def set_inheritance(obj_name, enabled, obj_type="file", clear=False):
    """
    Enable or disable an objects inheritance.

    Args:

        obj_name (str):
            The name of the object

        enabled (bool):
            True to enable inheritance, False to disable

        obj_type (Optional[str]):
            The type of object. Only three objects allow inheritance. Valid
            objects are:

            - file (default): This is a file or directory
            - registry
            - registry32 (for WOW64)

        clear (Optional[bool]):
            True to clear existing ACEs, False to keep existing ACEs.
            Default is False

    Returns:
        bool: True if successful, otherwise an Error

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.set_inheritance('C:\\Temp', False)
    """
    if obj_type not in ["file", "registry", "registry32"]:
        raise SaltInvocationError(
            "obj_type called with incorrect parameter: {}".format(obj_name)
        )

    if clear:
        obj_dacl = dacl(obj_type=obj_type)
    else:
        obj_dacl = dacl(obj_name, obj_type)

    return obj_dacl.save(obj_name, not enabled)


def get_inheritance(obj_name, obj_type="file"):
    """
    Get an object's inheritance.

    Args:

        obj_name (str):
            The name of the object

        obj_type (Optional[str]):
            The type of object. Only three object types allow inheritance. Valid
            objects are:

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
    """
    obj_dacl = dacl(obj_name=obj_name, obj_type=obj_type)
    inherited = win32security.INHERITED_ACE

    for i in range(0, obj_dacl.dacl.GetAceCount()):
        ace = obj_dacl.dacl.GetAce(i)
        if ace[0][1] & inherited == inherited:
            return True

    return False


def copy_security(
    source,
    target,
    obj_type="file",
    copy_owner=True,
    copy_group=True,
    copy_dacl=True,
    copy_sacl=True,
):
    r"""
    Copy the security descriptor of the Source to the Target. You can specify a
    specific portion of the security descriptor to copy using one of the
    `copy_*` parameters.

    .. note::
        At least one `copy_*` parameter must be ``True``

    .. note::
        The user account running this command must have the following
        privileges:

        - SeTakeOwnershipPrivilege
        - SeRestorePrivilege
        - SeSecurityPrivilege

    Args:

        source (str):
            The full path to the source. This is where the security info will be
            copied from

        target (str):
            The full path to the target. This is where the security info will be
            applied

        obj_type (str): file
            The type of object to query. This value changes the format of the
            ``obj_name`` parameter as follows:
            - file: indicates a file or directory
                - a relative path, such as ``FileName.txt`` or ``..\FileName``
                - an absolute path, such as ``C:\DirName\FileName.txt``
                - A UNC name, such as ``\\ServerName\ShareName\FileName.txt``
            - service: indicates the name of a Windows service
            - printer: indicates the name of a printer
            - registry: indicates a registry key
                - Uses the following literal strings to denote the hive:
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
                - Should be in the format of ``HIVE\Path\To\Key``. For example,
                    ``HKLM\SOFTWARE\Windows``
            - registry32: indicates a registry key under WOW64. Formatting is
                the same as it is for ``registry``
            - share: indicates a network share

        copy_owner (bool): True
            ``True`` copies owner information. Default is ``True``

        copy_group (bool): True
            ``True`` copies group information. Default is ``True``

        copy_dacl (bool): True
            ``True`` copies the DACL. Default is ``True``

        copy_sacl (bool): True
            ``True`` copies the SACL. Default is ``True``

    Returns:
        bool: ``True`` if successful

    Raises:
        SaltInvocationError: When parameters are invalid
        CommandExecutionError: On failure to set security

    Usage:

    .. code-block:: python

        salt.utils.win_dacl.copy_security(
            source='C:\\temp\\source_file.txt',
            target='C:\\temp\\target_file.txt',
            obj_type='file')

        salt.utils.win_dacl.copy_security(
            source='HKLM\\SOFTWARE\\salt\\test_source',
            target='HKLM\\SOFTWARE\\salt\\test_target',
            obj_type='registry',
            copy_owner=False)
    """
    obj_dacl = dacl(obj_type=obj_type)
    if "registry" in obj_type.lower():
        source = obj_dacl.get_reg_name(source)
        log.info("Source converted to: %s", source)
        target = obj_dacl.get_reg_name(target)
        log.info("Target converted to: %s", target)

    # Set flags
    try:
        obj_type_flag = flags().obj_type[obj_type.lower()]
    except KeyError:
        raise SaltInvocationError('Invalid "obj_type" passed: {}'.format(obj_type))

    security_flags = 0
    if copy_owner:
        security_flags |= win32security.OWNER_SECURITY_INFORMATION
    if copy_group:
        security_flags |= win32security.GROUP_SECURITY_INFORMATION
    if copy_dacl:
        security_flags |= win32security.DACL_SECURITY_INFORMATION
    if copy_sacl:
        security_flags |= win32security.SACL_SECURITY_INFORMATION

    if not security_flags:
        raise SaltInvocationError(
            "One of copy_owner, copy_group, copy_dacl, or copy_sacl must be True"
        )

    # To set the owner to something other than the logged in user requires
    # SE_TAKE_OWNERSHIP_NAME and SE_RESTORE_NAME privileges
    # Enable them for the logged in user
    # Setup the privilege set
    new_privs = set()
    luid = win32security.LookupPrivilegeValue("", "SeTakeOwnershipPrivilege")
    new_privs.add((luid, win32con.SE_PRIVILEGE_ENABLED))
    luid = win32security.LookupPrivilegeValue("", "SeRestorePrivilege")
    new_privs.add((luid, win32con.SE_PRIVILEGE_ENABLED))
    luid = win32security.LookupPrivilegeValue("", "SeSecurityPrivilege")
    new_privs.add((luid, win32con.SE_PRIVILEGE_ENABLED))

    # Get the current token
    p_handle = win32api.GetCurrentProcess()
    t_handle = win32security.OpenProcessToken(
        p_handle, win32security.TOKEN_ALL_ACCESS | win32con.TOKEN_ADJUST_PRIVILEGES
    )

    # Enable the privileges
    win32security.AdjustTokenPrivileges(t_handle, 0, new_privs)

    # Load object Security Info from the Source
    sec = win32security.GetNamedSecurityInfo(source, obj_type_flag, security_flags)

    # The following return None if the corresponding flag is not set
    sd_sid = sec.GetSecurityDescriptorOwner()
    sd_gid = sec.GetSecurityDescriptorGroup()
    sd_dacl = sec.GetSecurityDescriptorDacl()
    sd_sacl = sec.GetSecurityDescriptorSacl()

    # Set Security info on the target
    try:
        win32security.SetNamedSecurityInfo(
            target, obj_type_flag, security_flags, sd_sid, sd_gid, sd_dacl, sd_sacl
        )
    except pywintypes.error as exc:
        raise CommandExecutionError(
            "Failed to set security info: {}".format(exc.strerror)
        )

    return True


def _check_perms(obj_name, obj_type, new_perms, access_mode, ret, test_mode=False):
    """
    Helper function used by ``check_perms`` for checking and setting Grant and
    Deny permissions.

    Args:

        obj_name (str):
            The name or full path to the object

        obj_type (Optional[str]):
            The type of object for which to check permissions. Default is 'file'

        new_perms (dict):
            A dictionary containing the user/group and the basic permissions to
            check/grant, ie: ``{'user': {'perms': 'basic_permission'}}``.

        access_mode (str):
            The access mode to set. Either ``grant`` or ``deny``

        ret (dict):
            A dictionary to append changes to and return. If not passed, will
            create a new dictionary to return.

        test_mode (bool):
            ``True`` will only return the changes that would be made. ``False``
            will make the changes as well as return the changes that would be
            made.

    Returns:
        dict: A dictionary of return data as expected by the state system
    """
    access_mode = access_mode.lower()
    perms_label = "{}_perms".format(access_mode)
    cur_perms = get_permissions(obj_name=obj_name, obj_type=obj_type)
    changes = {}
    for user in new_perms:
        applies_to_text = ""
        # Check that user exists:
        try:
            user_name = get_name(principal=user)
        except CommandExecutionError:
            ret["comment"].append(
                '{} Perms: User "{}" missing from Target System'.format(
                    access_mode.capitalize(), user
                )
            )
            continue

        # Get the proper applies_to text
        if user_name not in cur_perms["Not Inherited"]:
            changes.setdefault(user, {})
            changes[user]["permissions"] = new_perms[user]["perms"]
            if "applies_to" in new_perms[user]:
                changes[user]["applies_to"] = new_perms[user]["applies_to"]
        else:
            # Check existing permissions
            if not has_permissions(
                obj_name=obj_name,
                principal=user_name,
                permissions=new_perms[user]["perms"],
                access_mode=access_mode,
                obj_type=obj_type,
                exact=True,
            ):
                changes.setdefault(user, {})
                changes[user]["permissions"] = new_perms[user]["perms"]

                # Check existing propagation
                if "applies_to" in new_perms[user]:
                    applies_to = new_perms[user]["applies_to"]
                    at_flag = flags().ace_prop[obj_type][applies_to]
                    applies_to_text = flags().ace_prop[obj_type][at_flag]

                    # Is there a deny/grant permission set
                    if access_mode in cur_perms["Not Inherited"][user_name]:
                        # If the applies to settings are different, use the new one
                        if (
                            not cur_perms["Not Inherited"][user_name][access_mode][
                                "applies to"
                            ]
                            == applies_to_text
                        ):
                            changes.setdefault(user, {})
                            changes[user]["applies_to"] = applies_to

    if changes:
        ret["changes"].setdefault(perms_label, {})
        for user in changes:
            user_name = get_name(principal=user)

            if test_mode is True:
                ret["changes"][perms_label].setdefault(user, {})
                ret["changes"][perms_label][user] = changes[user]
            else:
                if not test_mode:
                    try:
                        set_permissions(
                            obj_name=obj_name,
                            principal=user_name,
                            permissions=changes[user]["permissions"],
                            access_mode=access_mode,
                            applies_to=changes[user].get("applies_to"),
                            obj_type=obj_type,
                        )
                        ret["changes"].setdefault(perms_label, {}).setdefault(user, {})
                        ret["changes"][perms_label][user] = changes[user]
                    except CommandExecutionError as exc:
                        ret["result"] = False
                        ret["comment"].append(
                            'Failed to change {} permissions for "{}" to {}\n'
                            "Error: {}".format(
                                access_mode, user, changes[user], exc.strerror
                            )
                        )

    return ret


def check_perms(
    obj_name,
    obj_type="file",
    ret=None,
    owner=None,
    grant_perms=None,
    deny_perms=None,
    inheritance=True,
    reset=False,
    test_mode=None,
):
    """
    Check owner and permissions for the passed directory. This function checks
    the permissions and sets them, returning the changes made.

    .. versionadded:: 2019.2.0

    Args:

        obj_name (str):
            The name or full path to the object

        obj_type (Optional[str]):
            The type of object for which to check permissions. Default is 'file'

        ret (dict):
            A dictionary to append changes to and return. If not passed, will
            create a new dictionary to return.

        owner (str):
            The owner to set for the directory.

        grant_perms (dict):
            A dictionary containing the user/group and the basic permissions to
            check/grant, ie: ``{'user': {'perms': 'basic_permission'}}``.
            Default is ``None``.

        deny_perms (dict):
            A dictionary containing the user/group and permissions to
            check/deny. Default is ``None``.

        inheritance (bool):
            ``True`` will enable inheritance from the parent object. ``False``
            will disable inheritance. Default is ``True``.

        reset (bool):
            ``True`` will clear the DACL and set only the permissions defined
             in ``grant_perms`` and ``deny_perms``. ``False`` append permissions
             to the existing DACL. Default is ``False``. This does NOT affect
            inherited permissions.

        test_mode (bool):
            ``True`` will only return the changes that would be made. ``False``
            will make the changes as well as return the changes that would be
            made.

    Returns:
        dict: A dictionary of changes that have been made

    Usage:

    .. code-block:: bash

        # You have to use __utils__ in order for __opts__ to be available

        # To see changes to ``C:\\Temp`` if the 'Users' group is given 'read & execute' permissions.
        __utils__['dacl.check_perms'](obj_name='C:\\Temp',
                                      obj_type='file',
                                      owner='Administrators',
                                      grant_perms={
                                          'Users': {
                                              'perms': 'read_execute'
                                          }
                                      })

        # Specify advanced attributes with a list
        __utils__['dacl.check_perms'](obj_name='C:\\Temp',
                                      obj_type='file',
                                      owner='Administrators',
                                      grant_perms={
                                          'jsnuffy': {
                                              'perms': [
                                                  'read_attributes',
                                                  'read_ea'
                                              ],
                                              'applies_to': 'files_only'
                                          }
                                      })
    """
    if test_mode is None:
        test_mode = __opts__["test"]

    # Validate obj_type
    if obj_type.lower() not in flags().obj_type:
        raise SaltInvocationError('Invalid "obj_type" passed: {}'.format(obj_type))

    obj_type = obj_type.lower()

    if not ret:
        ret = {"name": obj_name, "changes": {}, "comment": [], "result": True}
        orig_comment = ""
    else:
        orig_comment = ret["comment"]
        ret["comment"] = []

    # Check owner
    if owner:
        owner = get_name(principal=owner)
        current_owner = get_owner(obj_name=obj_name, obj_type=obj_type)
        if owner != current_owner:
            if test_mode is True:
                ret["changes"]["owner"] = owner
            else:
                try:
                    set_owner(obj_name=obj_name, principal=owner, obj_type=obj_type)
                    # grant_perms.setdefault(owner, {})
                    log.debug("Owner set to %s", owner)
                    ret["changes"]["owner"] = owner
                except CommandExecutionError:
                    ret["result"] = False
                    ret["comment"].append(
                        'Failed to change owner to "{}"'.format(owner)
                    )

    # Check inheritance
    if inheritance is not None:
        if not inheritance == get_inheritance(obj_name=obj_name, obj_type=obj_type):
            if test_mode is True:
                ret["changes"]["inheritance"] = inheritance
            else:
                try:
                    set_inheritance(
                        obj_name=obj_name, enabled=inheritance, obj_type=obj_type
                    )
                    log.debug(
                        "%s inheritance", "Enabling" if inheritance else "Disabling"
                    )
                    ret["changes"]["inheritance"] = inheritance
                except CommandExecutionError:
                    ret["result"] = False
                    ret["comment"].append(
                        'Failed to set inheritance for "{}" to {}'.format(
                            obj_name, inheritance
                        )
                    )

    # Check reset
    # If reset=True, which users will be removed as a result
    if reset:
        log.debug("Resetting permissions for %s", obj_name)
        cur_perms = get_permissions(obj_name=obj_name, obj_type=obj_type)
        for user_name in cur_perms["Not Inherited"]:
            # case insensitive dictionary search
            if user_name not in {get_name(k) for k in (grant_perms or {})}:
                if "grant" in cur_perms["Not Inherited"][user_name]:
                    ret["changes"].setdefault("remove_perms", {})
                    if test_mode is True:
                        ret["changes"]["remove_perms"].update(
                            {user_name: cur_perms["Not Inherited"][user_name]}
                        )
                    else:
                        rm_permissions(
                            obj_name=obj_name,
                            principal=user_name,
                            ace_type="grant",
                            obj_type=obj_type,
                        )
                        ret["changes"]["remove_perms"].update(
                            {user_name: cur_perms["Not Inherited"][user_name]}
                        )
            # case insensitive dictionary search
            if user_name not in {get_name(k) for k in (deny_perms or {})}:
                if "deny" in cur_perms["Not Inherited"][user_name]:
                    ret["changes"].setdefault("remove_perms", {})
                    if test_mode is True:
                        ret["changes"]["remove_perms"].update(
                            {user_name: cur_perms["Not Inherited"][user_name]}
                        )
                    else:
                        rm_permissions(
                            obj_name=obj_name,
                            principal=user_name,
                            ace_type="deny",
                            obj_type=obj_type,
                        )
                        ret["changes"]["remove_perms"].update(
                            {user_name: cur_perms["Not Inherited"][user_name]}
                        )

    # Check permissions
    log.debug("Getting current permissions for %s", obj_name)

    # Verify Deny Permissions
    if deny_perms is not None:
        ret = _check_perms(
            obj_name=obj_name,
            obj_type=obj_type,
            new_perms=deny_perms,
            access_mode="deny",
            ret=ret,
            test_mode=test_mode,
        )

    # Verify Grant Permissions
    if grant_perms is not None:
        ret = _check_perms(
            obj_name=obj_name,
            obj_type=obj_type,
            new_perms=grant_perms,
            access_mode="grant",
            ret=ret,
            test_mode=test_mode,
        )

    # Clean up after itself if reset is True
    # This is needed because currently adding a permission will also add all
    # Inherited Permissions as Not Inherited permissions. These will not be
    # added to the Changes dict, as that is handled above
    if reset and not test_mode:
        log.debug("Resetting permissions for %s", obj_name)
        cur_perms = get_permissions(obj_name=obj_name, obj_type=obj_type)
        for user_name in cur_perms["Not Inherited"]:
            # case insensitive dictionary search
            if user_name not in {get_name(k) for k in (grant_perms or {})}:
                if "grant" in cur_perms["Not Inherited"][user_name]:
                    rm_permissions(
                        obj_name=obj_name,
                        principal=user_name,
                        ace_type="grant",
                        obj_type=obj_type,
                    )
            # case insensitive dictionary search
            if user_name not in {get_name(k) for k in (deny_perms or {})}:
                if "deny" in cur_perms["Not Inherited"][user_name]:
                    rm_permissions(
                        obj_name=obj_name,
                        principal=user_name,
                        ace_type="deny",
                        obj_type=obj_type,
                    )

    # Re-add the Original Comment if defined
    if isinstance(orig_comment, str):
        if orig_comment:
            ret["comment"].insert(0, orig_comment)
    else:
        if orig_comment:
            ret["comment"] = orig_comment.extend(ret["comment"])

    ret["comment"] = "\n".join(ret["comment"])

    # Set result for test = True
    if test_mode and ret["changes"]:
        ret["result"] = None

    return ret


def _set_perms(obj_dacl, obj_type, new_perms, cur_perms, access_mode):
    obj_type = obj_type.lower()
    ret = {}
    for user in new_perms:
        # Check that user exists:
        try:
            user_name = get_name(user)
        except CommandExecutionError:
            log.debug(
                '%s Perms: User "%s" missing from Target System',
                access_mode.capitalize(),
                user,
            )
            continue

        # Get applies_to
        applies_to = None
        # Propagation only applies to file and registry object types
        if obj_type in ["file", "registry", "registry32"]:
            if "applies_to" not in new_perms[user]:
                # Get current "applies to" settings from the object
                if (
                    user_name in cur_perms["Not Inherited"]
                    and "deny" in cur_perms["Not Inherited"][user_name]
                ):
                    for flag in flags().ace_prop[obj_type]:
                        if (
                            flags().ace_prop[obj_type][flag]
                            == cur_perms["Not Inherited"][user_name]["deny"][
                                "applies to"
                            ]
                        ):
                            at_flag = flag
                            for flag1 in flags().ace_prop[obj_type]:
                                if flags().ace_prop[obj_type][flag1] == at_flag:
                                    applies_to = flag1
                if not applies_to:
                    # Propagation only applies to file and registry object types
                    if obj_type == "file":
                        applies_to = "this_folder_subfolders_files"
                    elif "registry" in obj_type:
                        applies_to = "this_key_subkeys"
            else:
                applies_to = new_perms[user]["applies_to"]

        # Set permissions
        if obj_dacl.add_ace(
            principal=user,
            access_mode=access_mode,
            permissions=new_perms[user]["perms"],
            applies_to=applies_to,
        ):
            ret[user] = new_perms[user]

    return ret


def set_perms(
    obj_name,
    obj_type="file",
    grant_perms=None,
    deny_perms=None,
    inheritance=True,
    reset=False,
):
    """
    Set permissions for the given path

    .. versionadded:: 2019.2.0

    Args:

        obj_name (str):
            The name or full path to the object

        obj_type (Optional[str]):
            The type of object for which to check permissions. Default is 'file'

        grant_perms (dict):
            A dictionary containing the user/group and the basic permissions to
            grant, ie: ``{'user': {'perms': 'basic_permission'}}``. You can also
            set the ``applies_to`` setting here. The default for ``applise_to``
            is ``this_folder_subfolders_files``. Specify another ``applies_to``
            setting like this:

            .. code-block:: yaml

                {'user': {'perms': 'full_control', 'applies_to': 'this_folder'}}

            To set advanced permissions use a list for the ``perms`` parameter,
            ie:

            .. code-block:: yaml

                {'user': {'perms': ['read_attributes', 'read_ea'], 'applies_to': 'this_folder'}}

            To see a list of available attributes and applies to settings see
            the documentation for salt.utils.win_dacl.

            A value of ``None`` will make no changes to the ``grant`` portion of
            the DACL. Default is ``None``.

        deny_perms (dict):
            A dictionary containing the user/group and permissions to deny along
            with the ``applies_to`` setting. Use the same format used for the
            ``grant_perms`` parameter. Remember, deny permissions supersede
            grant permissions.

            A value of ``None`` will make no changes to the ``deny`` portion of
            the DACL. Default is ``None``.

        inheritance (bool):
            If ``True`` the object will inherit permissions from the parent, if
            ``False``, inheritance will be disabled. Inheritance setting will
            not apply to parent directories if they must be created. Default is
            ``False``.

        reset (bool):
            If ``True`` the existing DCL will be cleared and replaced with the
            settings defined in this function. If ``False``, new entries will be
            appended to the existing DACL. Default is ``False``.

    Returns:
        bool: True if successful

    Raises:
        CommandExecutionError: If unsuccessful

    Usage:

    .. code-block:: bash

        import salt.utils.win_dacl

        # To grant the 'Users' group 'read & execute' permissions.
        salt.utils.win_dacl.set_perms(obj_name='C:\\Temp',
                                      obj_type='file',
                                      grant_perms={
                                          'Users': {
                                              'perms': 'read_execute'
                                          }
                                      })

        # Specify advanced attributes with a list
        salt.utils.win_dacl.set_perms(obj_name='C:\\Temp',
                                      obj_type='file',
                                      grant_perms={
                                          'jsnuffy': {
                                              'perms': [
                                                  'read_attributes',
                                                  'read_ea'
                                              ],
                                              'applies_to': 'this_folder_only'
                                          }
                                      }"
    """
    ret = {}

    if reset:
        # Get an empty DACL
        obj_dacl = dacl(obj_type=obj_type)

        # Get an empty perms dict
        cur_perms = {"Inherited": {}, "Not Inherited": {}}

    else:
        # Get the DACL for the directory
        obj_dacl = dacl(obj_name, obj_type=obj_type)

        # Get current file/folder permissions
        cur_perms = get_permissions(obj_name=obj_name, obj_type=obj_type)

    # Set 'deny' perms if any
    if deny_perms is not None:
        ret["deny"] = _set_perms(
            obj_dacl=obj_dacl,
            obj_type=obj_type,
            new_perms=deny_perms,
            cur_perms=cur_perms,
            access_mode="deny",
        )

    # Set 'grant' perms if any
    if grant_perms is not None:
        ret["grant"] = _set_perms(
            obj_dacl=obj_dacl,
            obj_type=obj_type,
            new_perms=grant_perms,
            cur_perms=cur_perms,
            access_mode="grant",
        )

    # Order the ACL
    obj_dacl.order_acl()

    # Save the DACL, setting the inheritance
    # you have to invert inheritance because dacl.save is looking for
    # protected. protected True means Inherited False...

    if obj_dacl.save(obj_name, not inheritance):
        return ret

    return {}
