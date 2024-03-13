"""
Windows Service module.

.. versionchanged:: 2016.11.0

    Rewritten to use PyWin32
"""

import fnmatch
import logging
import re
import time

import salt.utils.path
import salt.utils.platform
import salt.utils.win_service
from salt.exceptions import CommandExecutionError

try:
    import pywintypes
    import win32service
    import win32serviceutil

    HAS_WIN32_MODS = True
except ImportError:
    HAS_WIN32_MODS = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "service"

SERVICE_TYPE = salt.utils.win_service.SERVICE_TYPE
SERVICE_START_TYPE = salt.utils.win_service.SERVICE_START_TYPE
SERVICE_ERROR_CONTROL = salt.utils.win_service.SERVICE_ERROR_CONTROL


def __virtual__():
    """
    Only works on Windows systems with PyWin32 installed
    """
    if not salt.utils.platform.is_windows():
        return False, "Module win_service: module only works on Windows."

    if not HAS_WIN32_MODS:
        return False, "Module win_service: failed to load win32 modules"

    return __virtualname__


def _status_wait(service_name, end_time, service_states):
    """
    Helper function that will wait for the status of the service to match the
    provided status before an end time expires. Used for service stop and start

    .. versionadded:: 2017.7.9,2018.3.4

    Args:
        service_name (str):
            The name of the service

        end_time (float):
            A future time. e.g. time.time() + 10

        service_states (list):
            Services statuses to wait for as returned by info()

    Returns:
        dict: A dictionary containing information about the service.

    :codeauthor: Damon Atkins <https://github.com/damon-atkins>
    """
    info_results = info(service_name)

    while info_results["Status"] in service_states and time.time() < end_time:
        # From Microsoft: Do not wait longer than the wait hint. A good interval
        # is one-tenth of the wait hint but not less than 1 second and not more
        # than 10 seconds.
        # https://docs.microsoft.com/en-us/windows/desktop/services/starting-a-service
        # https://docs.microsoft.com/en-us/windows/desktop/services/stopping-a-service
        # Wait hint is in ms
        wait_time = info_results["Status_WaitHint"]
        # Convert to seconds or 0
        wait_time = wait_time / 1000 if wait_time else 0
        if wait_time < 1:
            wait_time = 1
        elif wait_time > 10:
            wait_time = 10

        time.sleep(wait_time)
        info_results = info(service_name)

    return info_results


def _cmd_quote(cmd):
    r"""
    Helper function to properly format the path to the binary for the service
    Must be wrapped in double quotes to account for paths that have spaces. For
    example:

    ``"C:\Program Files\Path\to\bin.exe"``

    Args:
        cmd (str): Full path to the binary

    Returns:
        str: Properly quoted path to the binary
    """
    # Remove all single and double quotes from the beginning and the end
    pattern = re.compile("^(\\\"|').*|.*(\\\"|')$")
    while pattern.match(cmd) is not None:
        cmd = cmd.strip('"').strip("'")
    # Ensure the path to the binary is wrapped in double quotes to account for
    # spaces in the path
    cmd = f'"{cmd}"'
    return cmd


def get_enabled():
    """
    Return a list of enabled services. Enabled is defined as a service that is
    marked to Auto Start.

    Returns:
        list: A list of enabled services

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_enabled
    """
    raw_services = _get_services()
    services = set()
    for service in raw_services:
        if info(service["ServiceName"])["StartType"] in ["Auto"]:
            services.add(service["ServiceName"])

    return sorted(services)


def get_disabled():
    """
    Return a list of disabled services. Disabled is defined as a service that is
    marked 'Disabled' or 'Manual'.

    Returns:
        list: A list of disabled services.

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_disabled
    """
    raw_services = _get_services()
    services = set()
    for service in raw_services:
        if info(service["ServiceName"])["StartType"] in ["Manual", "Disabled"]:
            services.add(service["ServiceName"])

    return sorted(services)


def available(name):
    """
    Check if a service is available on the system.

    Args:
        name (str): The name of the service to check

    Returns:
        bool: ``True`` if the service is available, ``False`` otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.available <service name>
    """
    for service in get_all():
        if name.lower() == service.lower():
            return True

    return False


def missing(name):
    """
    The inverse of service.available.

    Args:
        name (str): The name of the service to check

    Returns:
        bool: ``True`` if the service is missing, ``False`` otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.missing <service name>
    """
    return name not in get_all()


def _get_services():
    """
    Returns a list of all services on the system.
    """
    handle_scm = win32service.OpenSCManager(
        None, None, win32service.SC_MANAGER_ENUMERATE_SERVICE
    )

    try:
        services = win32service.EnumServicesStatusEx(handle_scm)
    except AttributeError:
        services = win32service.EnumServicesStatus(handle_scm)
    finally:
        win32service.CloseServiceHandle(handle_scm)

    return services


def get_all():
    """
    Return all installed services

    Returns:
        list: Returns a list of all services on the system.

    CLI Example:

    .. code-block:: bash

        salt '*' service.get_all
    """
    services = _get_services()

    ret = set()
    for service in services:
        ret.add(service["ServiceName"])

    return sorted(ret)


def get_service_name(*args):
    """
    The Display Name is what is displayed in Windows when services.msc is
    executed.  Each Display Name has an associated Service Name which is the
    actual name of the service.  This function allows you to discover the
    Service Name by returning a dictionary of Display Names and Service Names,
    or filter by adding arguments of Display Names.

    If no args are passed, return a dict of all services where the keys are the
    service Display Names and the values are the Service Names.

    If arguments are passed, create a dict of Display Names and Service Names

    Returns:
        dict: A dictionary of display names and service names

    CLI Examples:

    .. code-block:: bash

        salt '*' service.get_service_name
        salt '*' service.get_service_name 'Google Update Service (gupdate)' 'DHCP Client'
    """
    raw_services = _get_services()

    services = dict()
    for raw_service in raw_services:
        if args:
            if (
                raw_service["DisplayName"] in args
                or raw_service["ServiceName"] in args
                or raw_service["ServiceName"].lower() in args
            ):
                services[raw_service["DisplayName"]] = raw_service["ServiceName"]
        else:
            services[raw_service["DisplayName"]] = raw_service["ServiceName"]

    return services


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
    return salt.utils.win_service.info(name=name)


def start(name, timeout=90):
    """
    Start the specified service.

    .. warning::
        You cannot start a disabled service in Windows. If the service is
        disabled, it will be changed to ``Manual`` start.

    Args:
        name (str): The name of the service to start

        timeout (int):
            The time in seconds to wait for the service to start before
            returning. Default is 90 seconds

            .. versionadded:: 2017.7.9,2018.3.4

    Returns:
        bool: ``True`` if successful, otherwise ``False``. Also returns ``True``
            if the service is already started

    CLI Example:

    .. code-block:: bash

        salt '*' service.start <service name>
    """
    # Set the service to manual if disabled
    if disabled(name):
        modify(name, start_type="Manual")

    try:
        win32serviceutil.StartService(name)
    except pywintypes.error as exc:
        if exc.winerror != 1056:
            raise CommandExecutionError(f"Failed To Start {name}: {exc.strerror}")
        log.debug('Service "%s" is running', name)

    srv_status = _status_wait(
        service_name=name,
        end_time=time.time() + int(timeout),
        service_states=["Start Pending", "Stopped"],
    )

    return srv_status["Status"] == "Running"


def stop(name, timeout=90):
    """
    Stop the specified service

    Args:
        name (str): The name of the service to stop

        timeout (int):
            The time in seconds to wait for the service to stop before
            returning. Default is 90 seconds

            .. versionadded:: 2017.7.9,2018.3.4

    Returns:
        bool: ``True`` if successful, otherwise ``False``. Also returns ``True``
            if the service is already stopped

    CLI Example:

    .. code-block:: bash

        salt '*' service.stop <service name>
    """
    try:
        win32serviceutil.StopService(name)
    except pywintypes.error as exc:
        if exc.winerror != 1062:
            raise CommandExecutionError(f"Failed To Stop {name}: {exc.strerror}")
        log.debug('Service "%s" is not running', name)

    srv_status = _status_wait(
        service_name=name,
        end_time=time.time() + int(timeout),
        service_states=["Running", "Stop Pending"],
    )

    return srv_status["Status"] == "Stopped"


def restart(name, timeout=90):
    """
    Restart the named service. This issues a stop command followed by a start.

    Args:
        name: The name of the service to restart.

            .. note::
                If the name passed is ``salt-minion`` a scheduled task is
                created and executed to restart the salt-minion service.

        timeout (int):
            The time in seconds to wait for the service to stop and start before
            returning. Default is 90 seconds

            .. note::
                The timeout is cumulative meaning it is applied to the stop and
                then to the start command. A timeout of 90 could take up to 180
                seconds if the service is long in stopping and starting

            .. versionadded:: 2017.7.9,2018.3.4

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' service.restart <service name>
    """
    if "salt-minion" in name:
        create_win_salt_restart_task()
        return execute_salt_restart_task()

    return stop(name=name, timeout=timeout) and start(name=name, timeout=timeout)


def create_win_salt_restart_task():
    """
    Create a task in Windows task scheduler to enable restarting the salt-minion

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' service.create_win_salt_restart_task()
    """
    # Updated to use full name for Nessus agent
    cmd = salt.utils.path.which("cmd")
    args = "/c ping -n 3 127.0.0.1 && net stop salt-minion && net start salt-minion"
    return __salt__["task.create_task"](
        name="restart-salt-minion",
        user_name="System",
        force=True,
        action_type="Execute",
        cmd=cmd,
        arguments=args,
        trigger_type="Once",
        start_date="1975-01-01",
        start_time="01:00",
    )


def execute_salt_restart_task():
    """
    Run the Windows Salt restart task

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' service.execute_salt_restart_task()
    """
    return __salt__["task.run"](name="restart-salt-minion")


def status(name, *args, **kwargs):
    """
    Return the status for a service.
    If the name contains globbing, a dict mapping service name to True/False
    values is returned.

    .. versionchanged:: 2018.3.0
        The service name can now be a glob (e.g. ``salt*``)

    .. versionchanged:: 3006.0
        Returns "Not Found" if the service is not found on the system

    Args:
        name (str): The name of the service to check

    Returns:
        bool: True if running, False otherwise
        dict: Maps service name to True if running, False otherwise
        str: Not Found if the service is not found on the system

    CLI Example:

    .. code-block:: bash

        salt '*' service.status <service name>
    """

    results = {}
    all_services = get_all()
    contains_globbing = bool(re.search(r"\*|\?|\[.+\]", name))
    if contains_globbing:
        services = fnmatch.filter(all_services, name)
    else:
        services = [name]
    for service in services:
        try:
            results[service] = info(service)["Status"] in ["Running", "Stop Pending"]
        except CommandExecutionError:
            results[service] = "Not Found"
    if contains_globbing:
        return results
    return results[name]


def getsid(name):
    """
    Return the SID for this windows service

    Args:
        name (str): The name of the service for which to return the SID

    Returns:
        str: A string representing the SID for the service

    CLI Example:

    .. code-block:: bash

        salt '*' service.getsid <service name>
    """
    return info(name)["sid"]


def modify(
    name,
    bin_path=None,
    exe_args=None,
    display_name=None,
    description=None,
    service_type=None,
    start_type=None,
    start_delayed=None,
    error_control=None,
    load_order_group=None,
    dependencies=None,
    account_name=None,
    account_password=None,
    run_interactive=None,
):
    # pylint: disable=anomalous-backslash-in-string
    """
    Modify a service's parameters. Changes will not be made for parameters that
    are not passed.

    .. versionadded:: 2016.11.0

    Args:
        name (str):
            The name of the service. Can be found using the
            ``service.get_service_name`` function

        bin_path (str):
            The path to the service executable. Backslashes must be escaped, eg:
            ``C:\\path\\to\\binary.exe``

        exe_args (str):
            Any arguments required by the service executable

        display_name (str):
            The name to display in the service manager

        description (str):
            The description to display for the service

        service_type (str):
            Specifies the service type. Default is ``own``. Valid options are as
            follows:

            - kernel: Driver service
            - filesystem: File system driver service
            - adapter: Adapter driver service (reserved)
            - recognizer: Recognizer driver service (reserved)
            - own (default): Service runs in its own process
            - share: Service shares a process with one or more other services

        start_type (str):
            Specifies the service start type. Valid options are as follows:

            - boot: Device driver that is loaded by the boot loader
            - system: Device driver that is started during kernel initialization
            - auto: Service that automatically starts
            - manual: Service must be started manually
            - disabled: Service cannot be started

        start_delayed (bool):
            Set the service to Auto(Delayed Start). Only valid if the start_type
            is set to ``Auto``. If service_type is not passed, but the service
            is already set to ``Auto``, then the flag will be set.

        error_control (str):
            The severity of the error, and action taken, if this service fails
            to start. Valid options are as follows:

            - normal: Error is logged and a message box is displayed
            - severe: Error is logged and computer attempts a restart with the
              last known good configuration
            - critical: Error is logged, computer attempts to restart with the
              last known good configuration, system halts on failure
            - ignore: Error is logged and startup continues, no notification is
              given to the user

        load_order_group (str):
            The name of the load order group to which this service belongs

        dependencies (list):
            A list of services or load ordering groups that must start before
            this service

        account_name (str):
            The name of the account under which the service should run. For
            ``own`` type services this should be in the ``domain\\username``
            format. The following are examples of valid built-in service
            accounts:

            - NT Authority\\LocalService
            - NT Authority\\NetworkService
            - NT Authority\\LocalSystem
            - .\\LocalSystem

        account_password (str):
            The password for the account name specified in ``account_name``. For
            the above built-in accounts, this can be None. Otherwise a password
            must be specified.

        run_interactive (bool):
            If this setting is True, the service will be allowed to interact
            with the user. Not recommended for services that run with elevated
            privileges.

    Returns:
        dict: a dictionary of changes made

    CLI Example:

    .. code-block:: bash

        salt '*' service.modify spooler start_type=disabled

    """
    # pylint: enable=anomalous-backslash-in-string
    # https://msdn.microsoft.com/en-us/library/windows/desktop/ms681987(v=vs.85).aspx
    # https://msdn.microsoft.com/en-us/library/windows/desktop/ms681988(v-vs.85).aspx
    handle_scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)

    try:
        handle_svc = win32service.OpenService(
            handle_scm,
            name,
            win32service.SERVICE_CHANGE_CONFIG | win32service.SERVICE_QUERY_CONFIG,
        )
    except pywintypes.error as exc:
        raise CommandExecutionError(f"Failed To Open {name}: {exc.strerror}")

    config_info = win32service.QueryServiceConfig(handle_svc)

    changes = dict()

    # Input Validation
    if bin_path is not None:
        # shlex.quote the path to the binary
        bin_path = _cmd_quote(bin_path)
        if exe_args is not None:
            bin_path = f"{bin_path} {exe_args}"
        changes["BinaryPath"] = bin_path

    if service_type is not None:
        if service_type.lower() in SERVICE_TYPE:
            service_type = SERVICE_TYPE[service_type.lower()]
            if run_interactive:
                service_type = service_type | win32service.SERVICE_INTERACTIVE_PROCESS
        else:
            raise CommandExecutionError(f"Invalid Service Type: {service_type}")
    else:
        if run_interactive is True:
            service_type = config_info[0] | win32service.SERVICE_INTERACTIVE_PROCESS
        elif run_interactive is False:
            service_type = config_info[0] ^ win32service.SERVICE_INTERACTIVE_PROCESS
        else:
            service_type = win32service.SERVICE_NO_CHANGE

    if service_type is not win32service.SERVICE_NO_CHANGE:
        flags = list()
        for bit in SERVICE_TYPE:
            if isinstance(bit, int) and service_type & bit:
                flags.append(SERVICE_TYPE[bit])

        changes["ServiceType"] = flags if flags else service_type

    if start_type is not None:
        if start_type.lower() in SERVICE_START_TYPE:
            start_type = SERVICE_START_TYPE[start_type.lower()]
        else:
            raise CommandExecutionError(f"Invalid Start Type: {start_type}")
        changes["StartType"] = SERVICE_START_TYPE[start_type]
    else:
        start_type = win32service.SERVICE_NO_CHANGE

    if error_control is not None:
        if error_control.lower() in SERVICE_ERROR_CONTROL:
            error_control = SERVICE_ERROR_CONTROL[error_control.lower()]
        else:
            raise CommandExecutionError(f"Invalid Error Control: {error_control}")
        changes["ErrorControl"] = SERVICE_ERROR_CONTROL[error_control]
    else:
        error_control = win32service.SERVICE_NO_CHANGE

    if account_name is not None:
        changes["ServiceAccount"] = account_name
    if account_name in ["LocalSystem", "LocalService", "NetworkService"]:
        account_password = ""

    if account_password is not None:
        changes["ServiceAccountPassword"] = "XXX-REDACTED-XXX"

    if load_order_group is not None:
        changes["LoadOrderGroup"] = load_order_group

    if dependencies is not None:
        changes["Dependencies"] = dependencies

    if display_name is not None:
        changes["DisplayName"] = display_name

    win32service.ChangeServiceConfig(
        handle_svc,
        service_type,
        start_type,
        error_control,
        bin_path,
        load_order_group,
        0,
        dependencies,
        account_name,
        account_password,
        display_name,
    )

    if description is not None:
        win32service.ChangeServiceConfig2(
            handle_svc, win32service.SERVICE_CONFIG_DESCRIPTION, description
        )
        changes["Description"] = description

    if start_delayed is not None:
        # You can only set delayed start for services that are set to auto start
        # Start type 2 is Auto
        # Start type -1 is no change
        if (start_type == -1 and config_info[1] == 2) or start_type == 2:
            win32service.ChangeServiceConfig2(
                handle_svc,
                win32service.SERVICE_CONFIG_DELAYED_AUTO_START_INFO,
                start_delayed,
            )
            changes["StartTypeDelayed"] = start_delayed
        else:
            changes["Warning"] = 'start_delayed: Requires start_type "auto"'

    win32service.CloseServiceHandle(handle_scm)
    win32service.CloseServiceHandle(handle_svc)

    return changes


def enable(name, start_type="auto", start_delayed=False, **kwargs):
    """
    Enable the named service to start at boot

    Args:
        name (str): The name of the service to enable.

        start_type (str): Specifies the service start type. Valid options are as
            follows:

            - boot: Device driver that is loaded by the boot loader
            - system: Device driver that is started during kernel initialization
            - auto: Service that automatically starts
            - manual: Service must be started manually
            - disabled: Service cannot be started

        start_delayed (bool): Set the service to Auto(Delayed Start). Only valid
            if the start_type is set to ``Auto``. If service_type is not passed,
            but the service is already set to ``Auto``, then the flag will be
            set.

    Returns:
        bool: ``True`` if successful, ``False`` otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.enable <service name>
    """

    modify(name, start_type=start_type, start_delayed=start_delayed)
    svcstat = info(name)
    if start_type.lower() == "auto":
        return (
            svcstat["StartType"].lower() == start_type.lower()
            and svcstat["StartTypeDelayed"] == start_delayed
        )
    else:
        return svcstat["StartType"].lower() == start_type.lower()


def disable(name, **kwargs):
    """
    Disable the named service to start at boot

    Args:
        name (str): The name of the service to disable

    Returns:
        bool: ``True`` if disabled, ``False`` otherwise

    CLI Example:

    .. code-block:: bash

        salt '*' service.disable <service name>
    """
    modify(name, start_type="Disabled")
    return info(name)["StartType"] == "Disabled"


def enabled(name, **kwargs):
    """
    Check to see if the named service is enabled to start on boot

    Args:
        name (str): The name of the service to check

    Returns:
        bool: True if the service is set to start

    CLI Example:

    .. code-block:: bash

        salt '*' service.enabled <service name>
    """
    return info(name)["StartType"] == "Auto"


def disabled(name):
    """
    Check to see if the named service is disabled to start on boot

    Args:
        name (str): The name of the service to check

    Returns:
        bool: True if the service is disabled

    CLI Example:

    .. code-block:: bash

        salt '*' service.disabled <service name>
    """
    return not enabled(name)


def create(
    name,
    bin_path,
    exe_args=None,
    display_name=None,
    description=None,
    service_type="own",
    start_type="manual",
    start_delayed=False,
    error_control="normal",
    load_order_group=None,
    dependencies=None,
    account_name=".\\LocalSystem",
    account_password=None,
    run_interactive=False,
    **kwargs,
):
    """
    Create the named service.

    .. versionadded:: 2015.8.0

    Args:

        name (str):
            Specifies the service name. This is not the display_name

        bin_path (str):
            Specifies the path to the service binary file. Backslashes must be
            escaped, eg: ``C:\\path\\to\\binary.exe``

        exe_args (str):
            Any additional arguments required by the service binary.

        display_name (str):
            The name to be displayed in the service manager. If not passed, the
            ``name`` will be used

        description (str):
            A description of the service

        service_type (str):
            Specifies the service type. Default is ``own``. Valid options are as
            follows:

            - kernel: Driver service
            - filesystem: File system driver service
            - adapter: Adapter driver service (reserved)
            - recognizer: Recognizer driver service (reserved)
            - own (default): Service runs in its own process
            - share: Service shares a process with one or more other services

        start_type (str):
            Specifies the service start type. Valid options are as follows:

            - boot: Device driver that is loaded by the boot loader
            - system: Device driver that is started during kernel initialization
            - auto: Service that automatically starts
            - manual (default): Service must be started manually
            - disabled: Service cannot be started

        start_delayed (bool):
            Set the service to Auto(Delayed Start). Only valid if the start_type
            is set to ``Auto``. If service_type is not passed, but the service
            is already set to ``Auto``, then the flag will be set. Default is
            ``False``

        error_control (str):
            The severity of the error, and action taken, if this service fails
            to start. Valid options are as follows:

            - normal (normal): Error is logged and a message box is displayed
            - severe: Error is logged and computer attempts a restart with the
              last known good configuration
            - critical: Error is logged, computer attempts to restart with the
              last known good configuration, system halts on failure
            - ignore: Error is logged and startup continues, no notification is
              given to the user

        load_order_group (str):
            The name of the load order group to which this service belongs

        dependencies (list):
            A list of services or load ordering groups that must start before
            this service

        account_name (str):
            The name of the account under which the service should run. For
            ``own`` type services this should be in the ``domain\\username``
            format. The following are examples of valid built-in service
            accounts:

            - NT Authority\\LocalService
            - NT Authority\\NetworkService
            - NT Authority\\LocalSystem
            - .\\LocalSystem

        account_password (str):
            The password for the account name specified in ``account_name``. For
            the above built-in accounts, this can be None. Otherwise a password
            must be specified.

        run_interactive (bool):
            If this setting is True, the service will be allowed to interact
            with the user. Not recommended for services that run with elevated
            privileges.

    Returns:
        dict: A dictionary containing information about the new service

    CLI Example:

    .. code-block:: bash

        salt '*' service.create <service name> <path to exe> display_name='<display name>'
    """
    if display_name is None:
        display_name = name

    # Test if the service already exists
    if name in get_all():
        raise CommandExecutionError(f"Service Already Exists: {name}")

    # shlex.quote the path to the binary
    bin_path = _cmd_quote(bin_path)
    if exe_args is not None:
        bin_path = f"{bin_path} {exe_args}"

    if service_type.lower() in SERVICE_TYPE:
        service_type = SERVICE_TYPE[service_type.lower()]
        if run_interactive:
            service_type = service_type | win32service.SERVICE_INTERACTIVE_PROCESS
    else:
        raise CommandExecutionError(f"Invalid Service Type: {service_type}")

    if start_type.lower() in SERVICE_START_TYPE:
        start_type = SERVICE_START_TYPE[start_type.lower()]
    else:
        raise CommandExecutionError(f"Invalid Start Type: {start_type}")

    if error_control.lower() in SERVICE_ERROR_CONTROL:
        error_control = SERVICE_ERROR_CONTROL[error_control.lower()]
    else:
        raise CommandExecutionError(f"Invalid Error Control: {error_control}")

    if start_delayed:
        if start_type != 2:
            raise CommandExecutionError(
                'Invalid Parameter: start_delayed requires start_type "auto"'
            )

    if account_name in [
        "LocalSystem",
        ".\\LocalSystem",
        "LocalService",
        ".\\LocalService",
        "NetworkService",
        ".\\NetworkService",
    ]:
        account_password = ""

    # Connect to Service Control Manager
    handle_scm = win32service.OpenSCManager(
        None, None, win32service.SC_MANAGER_ALL_ACCESS
    )

    # Create the service
    handle_svc = win32service.CreateService(
        handle_scm,
        name,
        display_name,
        win32service.SERVICE_ALL_ACCESS,
        service_type,
        start_type,
        error_control,
        bin_path,
        load_order_group,
        0,
        dependencies,
        account_name,
        account_password,
    )

    if description is not None:
        win32service.ChangeServiceConfig2(
            handle_svc, win32service.SERVICE_CONFIG_DESCRIPTION, description
        )

    if start_delayed is not None:
        # You can only set delayed start for services that are set to auto start
        # Start type 2 is Auto
        if start_type == 2:
            win32service.ChangeServiceConfig2(
                handle_svc,
                win32service.SERVICE_CONFIG_DELAYED_AUTO_START_INFO,
                start_delayed,
            )

    win32service.CloseServiceHandle(handle_scm)
    win32service.CloseServiceHandle(handle_svc)

    return info(name)


def delete(name, timeout=90):
    """
    Delete the named service

    Args:

        name (str): The name of the service to delete

        timeout (int):
            The time in seconds to wait for the service to be deleted before
            returning. This is necessary because a service must be stopped
            before it can be deleted. Default is 90 seconds

            .. versionadded:: 2017.7.9,2018.3.4

    Returns:
        bool: ``True`` if successful, otherwise ``False``. Also returns ``True``
            if the service is not present

    CLI Example:

    .. code-block:: bash

        salt '*' service.delete <service name>
    """
    handle_scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)

    try:
        handle_svc = win32service.OpenService(
            handle_scm, name, win32service.SERVICE_ALL_ACCESS
        )
    except pywintypes.error as exc:
        win32service.CloseServiceHandle(handle_scm)
        if exc.winerror != 1060:
            raise CommandExecutionError(f"Failed to open {name}. {exc.strerror}")
        log.debug('Service "%s" is not present', name)
        return True

    try:
        win32service.DeleteService(handle_svc)
    except pywintypes.error as exc:
        raise CommandExecutionError(f"Failed to delete {name}. {exc.strerror}")
    finally:
        log.debug("Cleaning up")
        win32service.CloseServiceHandle(handle_scm)
        win32service.CloseServiceHandle(handle_svc)

    end_time = time.time() + int(timeout)
    while name in get_all() and time.time() < end_time:
        time.sleep(1)

    return name not in get_all()
