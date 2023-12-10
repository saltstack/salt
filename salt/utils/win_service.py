import salt.utils.platform
from salt.exceptions import CommandExecutionError

try:
    import pywintypes
    import win32security
    import win32service

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

SERVICE_TYPE = {
    1: "Kernel Driver",
    2: "File System Driver",
    4: "Adapter Driver",
    8: "Recognizer Driver",
    16: "Win32 Own Process",
    32: "Win32 Share Process",
    256: "Interactive",
    "kernel": 1,
    "filesystem": 2,
    "adapter": 4,
    "recognizer": 8,
    "own": 16,
    "share": 32,
}

SERVICE_CONTROLS = {
    1: "Stop",
    2: "Pause/Continue",
    4: "Shutdown",
    8: "Change Parameters",
    16: "Netbind Change",
    32: "Hardware Profile Change",
    64: "Power Event",
    128: "Session Change",
    256: "Pre-Shutdown",
    512: "Time Change",
    1024: "Trigger Event",
}

SERVICE_STATE = {
    1: "Stopped",
    2: "Start Pending",
    3: "Stop Pending",
    4: "Running",
    5: "Continue Pending",
    6: "Pause Pending",
    7: "Paused",
}

SERVICE_ERRORS = {0: "No Error", 1066: "Service Specific Error"}

SERVICE_START_TYPE = {
    "boot": 0,
    "system": 1,
    "auto": 2,
    "manual": 3,
    "disabled": 4,
    0: "Boot",
    1: "System",
    2: "Auto",
    3: "Manual",
    4: "Disabled",
}

SERVICE_ERROR_CONTROL = {
    0: "Ignore",
    1: "Normal",
    2: "Severe",
    3: "Critical",
    "ignore": 0,
    "normal": 1,
    "severe": 2,
    "critical": 3,
}

__virtualname__ = "win_service"


def __virtual__():
    """
    Only load if Win32 Libraries are installed
    """
    if not salt.utils.platform.is_windows():
        return False, "win_dacl: Requires Windows"

    if not HAS_WIN32:
        return False, "win_dacl: Requires pywin32"

    return __virtualname__


def info(name):
    """
    Get information about a service on the system

    Args:
        name (str): The name of the service. This is not the display name. Use
            ``get_service_name`` to find the service name.

    Returns:
        dict: A dictionary containing information about the service.

    CLI Example:

    .. code-block:: bash

        salt '*' service.info spooler
    """
    try:
        handle_scm = win32service.OpenSCManager(
            None, None, win32service.SC_MANAGER_CONNECT
        )
    except pywintypes.error as exc:
        raise CommandExecutionError(
            "Failed to connect to the SCM: {}".format(exc.strerror)
        )

    try:
        handle_svc = win32service.OpenService(
            handle_scm,
            name,
            win32service.SERVICE_ENUMERATE_DEPENDENTS
            | win32service.SERVICE_INTERROGATE
            | win32service.SERVICE_QUERY_CONFIG
            | win32service.SERVICE_QUERY_STATUS,
        )
    except pywintypes.error as exc:
        raise CommandExecutionError("Failed To Open {}: {}".format(name, exc.strerror))

    try:
        config_info = win32service.QueryServiceConfig(handle_svc)
        status_info = win32service.QueryServiceStatusEx(handle_svc)

        try:
            description = win32service.QueryServiceConfig2(
                handle_svc, win32service.SERVICE_CONFIG_DESCRIPTION
            )
        except pywintypes.error:
            description = "Failed to get description"

        delayed_start = win32service.QueryServiceConfig2(
            handle_svc, win32service.SERVICE_CONFIG_DELAYED_AUTO_START_INFO
        )
    finally:
        win32service.CloseServiceHandle(handle_scm)
        win32service.CloseServiceHandle(handle_svc)

    ret = dict()
    try:
        sid = win32security.LookupAccountName("", "NT Service\\{}".format(name))[0]
        ret["sid"] = win32security.ConvertSidToStringSid(sid)
    except pywintypes.error:
        ret["sid"] = "Failed to get SID"

    ret["BinaryPath"] = config_info[3]
    ret["LoadOrderGroup"] = config_info[4]
    ret["TagID"] = config_info[5]
    ret["Dependencies"] = config_info[6]
    ret["ServiceAccount"] = config_info[7]
    ret["DisplayName"] = config_info[8]
    ret["Description"] = description
    ret["Status_ServiceCode"] = status_info["ServiceSpecificExitCode"]
    ret["Status_CheckPoint"] = status_info["CheckPoint"]
    ret["Status_WaitHint"] = status_info["WaitHint"]
    ret["StartTypeDelayed"] = delayed_start

    flags = list()
    for bit in SERVICE_TYPE:
        if isinstance(bit, int):
            if config_info[0] & bit:
                flags.append(SERVICE_TYPE[bit])

    ret["ServiceType"] = flags if flags else config_info[0]

    flags = list()
    for bit in SERVICE_CONTROLS:
        if status_info["ControlsAccepted"] & bit:
            flags.append(SERVICE_CONTROLS[bit])

    ret["ControlsAccepted"] = flags if flags else status_info["ControlsAccepted"]

    try:
        ret["Status_ExitCode"] = SERVICE_ERRORS[status_info["Win32ExitCode"]]
    except KeyError:
        ret["Status_ExitCode"] = status_info["Win32ExitCode"]

    try:
        ret["StartType"] = SERVICE_START_TYPE[config_info[1]]
    except KeyError:
        ret["StartType"] = config_info[1]

    try:
        ret["ErrorControl"] = SERVICE_ERROR_CONTROL[config_info[2]]
    except KeyError:
        ret["ErrorControl"] = config_info[2]

    try:
        ret["Status"] = SERVICE_STATE[status_info["CurrentState"]]
    except KeyError:
        ret["Status"] = status_info["CurrentState"]

    return ret
