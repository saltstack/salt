"""
Win System Utils

Functions shared with salt.modules.win_system and salt.grains.pending_reboot

.. versionadded:: 3001
"""

# NOTE: DO NOT USE RAW STRINGS IN THIS MODULE! UNICODE_LITERALS DOES NOT PLAY
# NICELY WITH RAW STRINGS CONTAINING \u or \U.

import logging

import salt.utils.win_reg
import salt.utils.win_update

try:
    import win32api
    import win32con

    HAS_WIN32_MODS = True
except ImportError:
    HAS_WIN32_MODS = False


log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "win_system"
MINION_VOLATILE_KEY = "SYSTEM\\CurrentControlSet\\Services\\salt-minion\\Volatile-Data"
REBOOT_REQUIRED_NAME = "Reboot required"


def __virtual__():
    """
    Only works on Windows systems
    """
    if not salt.utils.platform.is_windows():
        return (
            False,
            "win_system salt util failed to load: "
            "The util will only run on Windows systems",
        )
    if not HAS_WIN32_MODS:
        return (
            False,
            "win_system salt util failed to load: "
            "The util will only run on Windows systems",
        )
    return __virtualname__


def get_computer_name():
    """
    Get the Windows computer name. Uses the win32api to get the current computer
    name.

    .. versionadded:: 3001

    Returns:
        str: Returns the computer name if found. Otherwise returns ``False``.

    Example:

    .. code-block:: python

        import salt.utils.win_system
        salt.utils.win_system.get_computer_name()
    """
    name = win32api.GetComputerNameEx(win32con.ComputerNamePhysicalDnsHostname)
    return name if name else False


def get_pending_computer_name():
    """
    Get a pending computer name. If the computer name has been changed, and the
    change is pending a system reboot, this function will return the pending
    computer name. Otherwise, ``None`` will be returned. If there was an error
    retrieving the pending computer name, ``False`` will be returned, and an
    error message will be logged to the minion log.

    .. versionadded:: 3001

    Returns:
        str:
            Returns the pending name if pending restart. Returns ``None`` if not
            pending restart.

    Example:

    .. code-block:: python

        import salt.utils.win_system
        salt.utils.win_system.get_pending_computer_name()
    """
    current = get_computer_name()
    try:
        pending = salt.utils.win_reg.read_value(
            hive="HKLM",
            key="SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
            vname="NV Hostname",
        )["vdata"]
    except TypeError:
        # This should never happen as the above key and vname are system names
        # and should always be present
        return None
    if pending:
        return pending if pending.lower() != current.lower() else None


def get_pending_component_servicing():
    """
    Determine whether there are pending Component Based Servicing tasks that
    require a reboot.

    If any the following registry keys exist then a reboot is pending:

    ``HKLM:\\\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending``
    ``HKLM:\\\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootInProgress``
    ``HKLM:\\\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\PackagesPending``

    .. versionadded:: 3001

    Returns:
        bool: ``True`` if there are pending Component Based Servicing tasks,
        otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' system.get_pending_component_servicing
    """
    # So long as one of the registry keys exists, a reboot is pending
    base_key = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing"
    sub_keys = ("RebootPending", "RebootInProgress", "PackagesPending")
    for sub_key in sub_keys:
        key = "\\".join((base_key, sub_key))
        if salt.utils.win_reg.key_exists(hive="HKLM", key=key):
            return True

    return False


def get_pending_domain_join():
    """
    Determine whether there is a pending domain join action that requires a
    reboot.

    If any the following registry keys exist then a reboot is pending:

    ``HKLM:\\\\SYSTEM\\CurrentControlSet\\Services\\Netlogon\\AvoidSpnSet``
    ``HKLM:\\\\SYSTEM\\CurrentControlSet\\Services\\Netlogon\\JoinDomain``

    .. versionadded:: 3001

    Returns:
        bool: ``True`` if there is a pending domain join action, otherwise
        ``False``

    Example:

    .. code-block:: python

        import salt.utils.win_system
        salt.utils.win_system.get_pending_domain_join()
    """
    base_key = "SYSTEM\\CurrentControlSet\\Services\\Netlogon"
    sub_keys = ("AvoidSpnSet", "JoinDomain")

    # If any keys are present then there is a reboot pending.
    for sub_key in sub_keys:
        key = "\\".join((base_key, sub_key))
        if salt.utils.win_reg.key_exists(hive="HKLM", key=key):
            return True

    return False


def get_pending_file_rename():
    """
    Determine whether there are pending file rename operations that require a
    reboot.

    A reboot is pending if any of the following value names exist and have value
    data set:

    - ``PendingFileRenameOperations``
    - ``PendingFileRenameOperations2``

    in the following registry key:

    ``HKLM:\\\\SYSTEM\\CurrentControlSet\\Control\\Session Manager``

    .. versionadded:: 3001

    Returns:
        bool: ``True`` if there are pending file rename operations, otherwise
        ``False``

    Example:

    .. code-block:: python

        import salt.utils.win_system
        salt.utils.win_system.get_pending_file_rename()
    """
    vnames = ("PendingFileRenameOperations", "PendingFileRenameOperations2")
    key = "SYSTEM\\CurrentControlSet\\Control\\Session Manager"
    for vname in vnames:
        reg_ret = salt.utils.win_reg.read_value(hive="HKLM", key=key, vname=vname)
        if reg_ret["success"]:
            if reg_ret["vdata"] and (reg_ret["vdata"] != "(value not set)"):
                return True
    return False


def get_pending_servermanager():
    """
    Determine whether there are pending Server Manager tasks that require a
    reboot.

    A reboot is pending if the ``CurrentRebootAttempts`` value name exists and
    has an integer value. The value name resides in the following registry key:

    ``HKLM:\\\\SOFTWARE\\Microsoft\\ServerManager``

    .. versionadded:: 3001

    Returns:
        bool: ``True`` if there are pending Server Manager tasks, otherwise
        ``False``

    Example:

    .. code-block:: python

        import salt.utils.win_system
        salt.utils.win_system.get_pending_servermanager()
    """
    vname = "CurrentRebootAttempts"
    key = "SOFTWARE\\Microsoft\\ServerManager"

    # There are situations where it's possible to have '(value not set)' as
    # the value data, and since an actual reboot won't be pending in that
    # instance, just catch instances where we try unsuccessfully to cast as int.

    reg_ret = salt.utils.win_reg.read_value(hive="HKLM", key=key, vname=vname)
    if reg_ret["success"]:
        try:
            if int(reg_ret["vdata"]) > 0:
                return True
        except ValueError:
            pass
    return False


def get_pending_dvd_reboot():
    """
    Determine whether the DVD Reboot flag is set.

    The system requires a reboot if the ``DVDRebootSignal`` value name exists
    at the following registry location:

    ``HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\RunOnce``

    .. versionadded:: 3001

    Returns:
        bool: ``True`` if the above condition is met, otherwise ``False``

    Example:

    .. code-block:: python

        import salt.utils.win_system
        salt.utils.win_system.get_pending_dvd_reboot()
    """
    # So long as the registry key exists, a reboot is pending.
    return salt.utils.win_reg.value_exists(
        hive="HKLM",
        key="SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\RunOnce",
        vname="DVDRebootSignal",
    )


def get_pending_update():
    """
    Determine whether there are pending updates that require a reboot.

    If either of the following registry keys exists, a reboot is pending:

    ``HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired``
    ``HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\PostRebootReporting``

    .. versionadded:: 3001

    Returns:
        bool: ``True`` if any of the above conditions are met, otherwise
        ``False``

    Example:

    .. code-block:: python

        import salt.utils.win_system
        salt.utils.win_system.get_pending_update()
    """
    # So long as any of the registry keys exists, a reboot is pending.
    base_key = (
        "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update"
    )
    sub_keys = ("RebootRequired", "PostRebootReporting")
    for sub_key in sub_keys:
        key = "\\".join((base_key, sub_key))
        if salt.utils.win_reg.key_exists(hive="HKLM", key=key):
            return True

    return False


def get_reboot_required_witnessed():
    """
    Determine if at any time during the current boot session the salt minion
    witnessed an event indicating that a reboot is required.

    This function will return ``True`` if an install completed with exit
    code 3010 during the current boot session and can be extended where
    appropriate in the future.

    If the ``Reboot required`` value name exists in the following location and
    has a value of ``1`` then the system is pending reboot:

    ``HKLM:\\\\SYSTEM\\CurrentControlSet\\Services\\salt-minion\\Volatile-Data``

    .. versionadded:: 3001

    Returns:
        bool: ``True`` if the ``Requires reboot`` registry flag is set to ``1``,
        otherwise ``False``

    Example:

    .. code-block:: python

        import salt.utils.win_system
        salt.utils.win_system.get_reboot_required_witnessed()

    """
    value_dict = salt.utils.win_reg.read_value(
        hive="HKLM", key=MINION_VOLATILE_KEY, vname=REBOOT_REQUIRED_NAME
    )
    return value_dict["vdata"] == 1


def set_reboot_required_witnessed():
    """
    This function is used to remember that an event indicating that a reboot is
    required was witnessed. This function relies on the salt-minion's ability to
    create the following volatile registry key in the *HKLM* hive:

       *SYSTEM\\CurrentControlSet\\Services\\salt-minion\\Volatile-Data*

    Because this registry key is volatile, it will not persist beyond the
    current boot session. Also, in the scope of this key, the name *'Reboot
    required'* will be assigned the value of *1*.

    For the time being, this function is being used whenever an install
    completes with exit code 3010 and can be extended where appropriate in the
    future.

    .. versionadded:: 3001

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    Example:

    .. code-block:: python

        import salt.utils.win_system
        salt.utils.win_system.set_reboot_required_witnessed()
    """
    return salt.utils.win_reg.set_value(
        hive="HKLM",
        key=MINION_VOLATILE_KEY,
        volatile=True,
        vname=REBOOT_REQUIRED_NAME,
        vdata=1,
        vtype="REG_DWORD",
    )


def get_pending_update_exe_volatile():
    """
    Determine whether there is a volatile update exe that requires a reboot.

    Checks ``HKLM:\\Microsoft\\Updates``. If the ``UpdateExeVolatile`` value
    name is anything other than 0 there is a reboot pending

    .. versionadded:: 3001

    Returns:
        bool: ``True`` if there is a volatile exe, otherwise ``False``

    Example:

    .. code-block:: python

        import salt.utils.win_system
        salt.utils.win_system.get_pending_update_exe_volatile()
    """
    key = "SOFTWARE\\Microsoft\\Updates"
    reg_ret = salt.utils.win_reg.read_value(
        hive="HKLM", key=key, vname="UpdateExeVolatile"
    )
    if reg_ret["success"]:
        try:
            if int(reg_ret["vdata"]) != 0:
                return True
        except ValueError:
            pass
    return False


def get_pending_windows_update():
    """
    Check the Windows Update system for a pending reboot state.

    This leverages the Windows Update System to determine if the system is
    pending a reboot.

    .. versionadded:: 3001

    Returns:
        bool: ``True`` if the Windows Update system reports a pending update,
        otherwise ``False``

    Example:

    .. code-block:: python

        import salt.utils.win_system
        salt.utils.win_system.get_pending_windows_update()
    """
    return salt.utils.win_update.needs_reboot()


def get_pending_reboot():
    """
    Determine whether there is a reboot pending.

    .. versionadded:: 3001

    Returns:
        bool: ``True`` if the system is pending reboot, otherwise ``False``

    Example:

    .. code-block:: python

        import salt.utils.win_system
        salt.utils.win_system.get_pending_reboot()
    """
    # Order the checks for reboot pending in most to least likely.
    checks = (
        get_pending_update,
        get_pending_windows_update,
        get_pending_update_exe_volatile,
        get_pending_file_rename,
        get_pending_servermanager,
        get_pending_component_servicing,
        get_pending_dvd_reboot,
        get_reboot_required_witnessed,
        get_pending_computer_name,
        get_pending_domain_join,
    )

    for check in checks:
        if check():
            return True

    return False


def get_pending_reboot_details():
    """
    Determine which check is signalling that the system is pending a reboot.
    Useful in determining why your system is signalling that it needs a reboot.

    .. versionadded:: 3001

    Returns:
        dict: A dictionary of the results of each function that checks for a
        pending reboot

    Example:

    .. code-block:: python

        import salt.utils.win_system
        salt.utils.win_system.get_pending_reboot_details()
    """
    return {
        "Pending Component Servicing": get_pending_component_servicing(),
        "Pending Computer Rename": get_pending_computer_name() is not None,
        "Pending DVD Reboot": get_pending_dvd_reboot(),
        "Pending File Rename": get_pending_file_rename(),
        "Pending Join Domain": get_pending_domain_join(),
        "Pending ServerManager": get_pending_servermanager(),
        "Pending Update": get_pending_update(),
        "Pending Windows Update": get_pending_windows_update(),
        "Reboot Required Witnessed": get_reboot_required_witnessed(),
        "Volatile Update Exe": get_pending_update_exe_volatile(),
    }
