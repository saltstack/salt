# https://msdn.microsoft.com/en-us/library/windows/desktop/aa383608(v=vs.85).aspx
"""
Windows Task Scheduler Module
.. versionadded:: 2016.3.0

A module for working with the Windows Task Scheduler.
You can add and edit existing tasks.
You can add and clear triggers and actions.
You can list all tasks, folders, triggers, and actions.
"""

import logging
import time
from datetime import datetime

import salt.utils.platform
import salt.utils.winapi
from salt.exceptions import ArgumentValueError, CommandExecutionError

try:
    import pythoncom
    import pywintypes
    import win32com.client

    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "task"

# Define Constants
# TASK_ACTION_TYPE
TASK_ACTION_EXEC = 0
TASK_ACTION_COM_HANDLER = 5
TASK_ACTION_SEND_EMAIL = 6
TASK_ACTION_SHOW_MESSAGE = 7

# TASK_COMPATIBILITY
TASK_COMPATIBILITY_AT = 0
TASK_COMPATIBILITY_V1 = 1
TASK_COMPATIBILITY_V2 = 2
TASK_COMPATIBILITY_V3 = 3

# TASK_CREATION
TASK_VALIDATE_ONLY = 0x1
TASK_CREATE = 0x2
TASK_UPDATE = 0x4
TASK_CREATE_OR_UPDATE = 0x6
TASK_DISABLE = 0x8
TASK_DONT_ADD_PRINCIPAL_ACE = 0x10
TASK_IGNORE_REGISTRATION_TRIGGERS = 0x20

# TASK_INSTANCES_POLICY
TASK_INSTANCES_PARALLEL = 0
TASK_INSTANCES_QUEUE = 1
TASK_INSTANCES_IGNORE_NEW = 2
TASK_INSTANCES_STOP_EXISTING = 3

# TASK_LOGON_TYPE
TASK_LOGON_NONE = 0
TASK_LOGON_PASSWORD = 1
TASK_LOGON_S4U = 2
TASK_LOGON_INTERACTIVE_TOKEN = 3
TASK_LOGON_GROUP = 4
TASK_LOGON_SERVICE_ACCOUNT = 5
TASK_LOGON_INTERACTIVE_TOKEN_OR_PASSWORD = 6

# TASK_RUNLEVEL_TYPE
TASK_RUNLEVEL_LUA = 0
TASK_RUNLEVEL_HIGHEST = 1

# TASK_STATE_TYPE
TASK_STATE_UNKNOWN = 0
TASK_STATE_DISABLED = 1
TASK_STATE_QUEUED = 2
TASK_STATE_READY = 3
TASK_STATE_RUNNING = 4

# TASK_TRIGGER_TYPE
TASK_TRIGGER_EVENT = 0
TASK_TRIGGER_TIME = 1
TASK_TRIGGER_DAILY = 2
TASK_TRIGGER_WEEKLY = 3
TASK_TRIGGER_MONTHLY = 4
TASK_TRIGGER_MONTHLYDOW = 5
TASK_TRIGGER_IDLE = 6
TASK_TRIGGER_REGISTRATION = 7
TASK_TRIGGER_BOOT = 8
TASK_TRIGGER_LOGON = 9
TASK_TRIGGER_SESSION_STATE_CHANGE = 11

duration = {
    "Immediately": "PT0M",
    "Indefinitely": "",
    "Do not wait": "PT0M",
    "15 seconds": "PT15S",
    "30 seconds": "PT30S",
    "1 minute": "PT1M",
    "5 minutes": "PT5M",
    "10 minutes": "PT10M",
    "15 minutes": "PT15M",
    "30 minutes": "PT30M",
    "1 hour": "PT1H",
    "2 hours": "PT2H",
    "4 hours": "PT4H",
    "8 hours": "PT8H",
    "12 hours": "PT12H",
    "1 day": ["P1D", "PT24H"],
    "3 days": ["P3D", "PT72H"],
    "30 days": "P30D",
    "90 days": "P90D",
    "180 days": "P180D",
    "365 days": "P365D",
}

action_types = {
    "Execute": TASK_ACTION_EXEC,
    "Email": TASK_ACTION_SEND_EMAIL,
    "Message": TASK_ACTION_SHOW_MESSAGE,
}

trigger_types = {
    "Event": TASK_TRIGGER_EVENT,
    "Once": TASK_TRIGGER_TIME,
    "Daily": TASK_TRIGGER_DAILY,
    "Weekly": TASK_TRIGGER_WEEKLY,
    "Monthly": TASK_TRIGGER_MONTHLY,
    "MonthlyDay": TASK_TRIGGER_MONTHLYDOW,
    "OnIdle": TASK_TRIGGER_IDLE,
    "OnTaskCreation": TASK_TRIGGER_REGISTRATION,
    "OnBoot": TASK_TRIGGER_BOOT,
    "OnLogon": TASK_TRIGGER_LOGON,
    "OnSessionChange": TASK_TRIGGER_SESSION_STATE_CHANGE,
}

states = {
    TASK_STATE_UNKNOWN: "Unknown",
    TASK_STATE_DISABLED: "Disabled",
    TASK_STATE_QUEUED: "Queued",
    TASK_STATE_READY: "Ready",
    TASK_STATE_RUNNING: "Running",
}

instances = {
    "Parallel": TASK_INSTANCES_PARALLEL,
    "Queue": TASK_INSTANCES_QUEUE,
    "No New Instance": TASK_INSTANCES_IGNORE_NEW,
    "Stop Existing": TASK_INSTANCES_STOP_EXISTING,
}

results = {
    0x0: "The operation completed successfully",
    0x1: "Incorrect or unknown function called",
    0x2: "File not found",
    0xA: "The environment is incorrect",
    0x41300: "Task is ready to run at its next scheduled time",
    0x41301: "Task is currently running",
    0x41302: "Task is disabled",
    0x41303: "Task has not yet run",
    0x41304: "There are no more runs scheduled for this task",
    0x41306: "Task was terminated by the user",
    0x8004130F: "Credentials became corrupted",
    0x8004131F: "An instance of this task is already running",
    0x800710E0: "The operator or administrator has refused the request",
    0x800704DD: "The service is not available (Run only when logged in?)",
    0xC000013A: "The application terminated as a result of CTRL+C",
    0xC06D007E: "Unknown software exception",
}


def __virtual__():
    """
    Only works on Windows systems
    """
    if salt.utils.platform.is_windows():
        if not HAS_DEPENDENCIES:
            log.warning("Could not load dependencies for %s", __virtualname__)
        return __virtualname__
    return False, "Module win_task: module only works on Windows systems"


def _signed_to_unsigned_int32(code):
    """
    Convert negative result and error codes from win32com
    """
    if code < 0:
        code = code + 2**32
    return code


def _get_date_time_format(dt_string):
    """
    Copied from win_system.py (_get_date_time_format)

    Function that detects the date/time format for the string passed.

    :param str dt_string:
        A date/time string

    :return: The format of the passed dt_string
    :rtype: str
    """
    valid_formats = [
        "%I:%M:%S %p",
        "%I:%M %p",
        "%H:%M:%S",
        "%H:%M",
        "%Y-%m-%d",
        "%m-%d-%y",
        "%m-%d-%Y",
        "%m/%d/%y",
        "%m/%d/%Y",
        "%Y/%m/%d",
    ]
    for dt_format in valid_formats:
        try:
            datetime.strptime(dt_string, dt_format)
            return dt_format
        except ValueError:
            continue
    return False


def _get_date_value(date):
    """
    Function for dealing with PyTime values with invalid dates. ie: 12/30/1899
    which is the windows task scheduler value for Never

    :param obj date: A PyTime object

    :return: A string value representing the date or the word "Never" for
    invalid date strings
    :rtype: str
    """
    try:
        return f"{date}"
    except ValueError:
        return "Never"


def _reverse_lookup(dictionary, value):
    """
    Lookup the key in a dictionary by its value. Will return the first match.

    :param dict dictionary: The dictionary to search

    :param str value: The value to search for.

    :return: Returns the first key to match the value
    :rtype: str
    """
    value_index = -1
    for idx, dict_value in enumerate(dictionary.values()):
        if isinstance(dict_value, list):
            if value in dict_value:
                value_index = idx
                break
        elif value == dict_value:
            value_index = idx
            break

    if value_index < 0:
        return "invalid value"
    return list(dictionary)[value_index]


def _lookup_first(dictionary, key):
    """
    Lookup the first value given a key. Returns the first value if the key
    refers to a list or the value itself.

    :param dict dictionary: The dictionary to search

    :param str key: The key to get

    :return: Returns the first value available for the key
    :rtype: str
    """
    value = dictionary[key]
    if isinstance(value, list):
        return value[0]
    else:
        return value


def _save_task_definition(
    name, task_folder, task_definition, user_name, password, logon_type
):
    """
    Internal function to save the task definition.

    :param str name: The name of the task.

    :param str task_folder: The object representing the folder in which to save
    the task

    :param str task_definition: The object representing the task to be saved

    :param str user_name: The user_account under which to run the task

    :param str password: The password that corresponds to the user account

    :param int logon_type: The logon type for the task.

    :return: True if successful, False if not
    :rtype: bool
    """
    try:
        task_folder.RegisterTaskDefinition(
            name,
            task_definition,
            TASK_CREATE_OR_UPDATE,
            user_name,
            password,
            logon_type,
        )

        return True

    except pythoncom.com_error as error:
        hr, msg, exc, arg = error.args  # pylint: disable=W0633
        error_code = _signed_to_unsigned_int32(exc[5])
        fc = {
            0x8007007B: (
                "The filename, directory name, or volume label syntax is incorrect"
            ),
            0x80070002: "The system cannot find the file specified",
            0x80041319: "Required element or attribute missing",
            0x80041318: "Value incorrectly formatted or out of range",
            0x80020005: "Access denied",
        }
        try:
            failure_code = fc[error_code]
        except KeyError:
            failure_code = f"Unknown Failure: {hex(error_code)}"

        log.debug("Failed to modify task: %s", failure_code)

        return f"Failed to modify task: {failure_code}"


def list_tasks(location="\\"):
    r"""
    List all tasks located in a specific location in the task scheduler.

    Args:

        location (str):
            A string value representing the folder from which you want to list
            tasks. Default is ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

    Returns:
        list: Returns a list of tasks

    CLI Example:

    .. code-block:: bash

        # List all tasks in the default location
        salt 'minion-id' task.list_tasks

        # List all tasks in the Microsoft\XblGameSave Directory
        salt 'minion-id' task.list_tasks Microsoft\XblGameSave
    """
    # Create the task service object
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # Get the folder to list tasks from
        try:
            task_folder = task_service.GetFolder(location)
        except pywintypes.com_error:
            msg = f"Unable to load location: {location}"
            log.error(msg)
            raise CommandExecutionError(msg)

        tasks = task_folder.GetTasks(0)

        ret = []
        for task in tasks:
            ret.append(task.Name)

    return ret


def list_folders(location="\\"):
    r"""
    List all folders located in a specific location in the task scheduler.

    Args:

        location (str):
            A string value representing the folder from which you want to list
            tasks. Default is ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

    Returns:
        list: Returns a list of folders.

    CLI Example:

    .. code-block:: bash

        # List all folders in the default location
        salt 'minion-id' task.list_folders

        # List all folders in the Microsoft directory
        salt 'minion-id' task.list_folders Microsoft
    """
    # Create the task service object
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # Get the folder to list folders from
        task_folder = task_service.GetFolder(location)
        folders = task_folder.GetFolders(0)

        ret = []
        for folder in folders:
            ret.append(folder.Name)

    return ret


def list_triggers(name, location="\\"):
    r"""
    List all triggers that pertain to a task in the specified location.

    Args:

        name (str):
            The name of the task for which list triggers.

        location (str):
            A string value representing the location of the task from which to
            list triggers. Default is ``\`` which is the root for the task
            scheduler (``C:\Windows\System32\tasks``).

    Returns:
        list: Returns a list of triggers.

    CLI Example:

    .. code-block:: bash

        # List all triggers for a task in the default location
        salt 'minion-id' task.list_triggers <task_name>

        # List all triggers for the XblGameSaveTask in the Microsoft\XblGameSave
        # location
        salt '*' task.list_triggers XblGameSaveTask Microsoft\XblGameSave
    """
    # Create the task service object
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # Get the folder to list folders from
        task_folder = task_service.GetFolder(location)
        task_definition = task_folder.GetTask(name).Definition
        triggers = task_definition.Triggers

        ret = []
        for trigger in triggers:
            ret.append(trigger.Id)

    return ret


def list_actions(name, location="\\"):
    r"""
    List all actions that pertain to a task in the specified location.

    Args:

        name (str):
            The name of the task for which list actions.

        location (str):
            A string value representing the location of the task from which to
            list actions. Default is ``\`` which is the root for the task
            scheduler (``C:\Windows\System32\tasks``).

    Returns:
        list: Returns a list of actions.

    CLI Example:

    .. code-block:: bash

        # List all actions for a task in the default location
        salt 'minion-id' task.list_actions <task_name>

        # List all actions for the XblGameSaveTask in the Microsoft\XblGameSave
        # location
        salt 'minion-id' task.list_actions XblGameSaveTask Microsoft\XblGameSave
    """
    # Create the task service object
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # Get the folder to list folders from
        task_folder = task_service.GetFolder(location)
        task_definition = task_folder.GetTask(name).Definition
        actions = task_definition.Actions

        ret = []
        for action in actions:
            ret.append(action.Id)

    return ret


def create_task(
    name, location="\\", user_name="System", password=None, force=False, **kwargs
):
    r"""
    Create a new task in the designated location. This function has many keyword
    arguments that are not listed here. For additional arguments see:

        - :py:func:`edit_task`
        - :py:func:`add_action`
        - :py:func:`add_trigger`

    Args:

        name (str):
            The name of the task. This will be displayed in the task scheduler.

        location (str):
            A string value representing the location in which to create the
            task. Default is ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

        user_name (str):
            The user account under which to run the task. To specify the
            'System' account, use 'System'. The password will be ignored.

        password (str):
            The password to use for authentication. This should set the task to
            run whether the user is logged in or not, but is currently not
            working.

        force (bool):
            If the task exists, overwrite the existing task.

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' task.create_task <task_name> user_name=System force=True action_type=Execute cmd='del /Q /S C:\\Temp' trigger_type=Once start_date=2016-12-1 start_time='"01:00"'
    """
    # Check for existing task
    if name in list_tasks(location) and not force:
        # Connect to an existing task definition
        return f"{name} already exists"

    # connect to the task scheduler
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # Create a new task definition
        task_definition = task_service.NewTask(0)

        # Modify task settings
        edit_task(
            task_definition=task_definition,
            user_name=user_name,
            password=password,
            **kwargs,
        )

        # Add Action
        add_action(task_definition=task_definition, **kwargs)

        # Add Trigger
        add_trigger(task_definition=task_definition, **kwargs)

        # get the folder to create the task in
        task_folder = task_service.GetFolder(location)

        # Save the task
        _save_task_definition(
            name=name,
            task_folder=task_folder,
            task_definition=task_definition,
            user_name=task_definition.Principal.UserID,
            password=password,
            logon_type=task_definition.Principal.LogonType,
        )

    # Verify task was created
    return name in list_tasks(location)


def create_task_from_xml(
    name, location="\\", xml_text=None, xml_path=None, user_name="System", password=None
):
    r"""
    Create a task based on XML. Source can be a file or a string of XML.

    Args:

        name (str):
            The name of the task. This will be displayed in the task scheduler.

        location (str):
            A string value representing the location in which to create the
            task. Default is ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

        xml_text (str):
            A string of xml representing the task to be created. This will be
            overridden by ``xml_path`` if passed.

        xml_path (str):
            The path to an XML file on the local system containing the xml that
            defines the task. This will override ``xml_text``

        user_name (str):
            The user account under which to run the task. To specify the
            'System' account, use 'System'. The password will be ignored.

        password (str):
            The password to use for authentication. This should set the task to
            run whether the user is logged in or not, but is currently not
            working.

    Returns:
        bool: ``True`` if successful, otherwise ``False``
        str: A string with the error message if there is an error

    Raises:
        ArgumentValueError: If arguments are invalid
        CommandExecutionError

    CLI Example:

    .. code-block:: bash

        salt '*' task.create_task_from_xml <task_name> xml_path=C:\task.xml
    """
    # Check for existing task
    if name in list_tasks(location):
        # Connect to an existing task definition
        return f"{name} already exists"

    if not xml_text and not xml_path:
        raise ArgumentValueError("Must specify either xml_text or xml_path")

    # Create the task service object
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # Load xml from file, overrides xml_text
        # Need to figure out how to load contents of xml
        if xml_path:
            xml_text = xml_path

        # Get the folder to list folders from
        task_folder = task_service.GetFolder(location)

        # Determine logon type
        if user_name:
            if user_name.lower() == "system":
                logon_type = TASK_LOGON_SERVICE_ACCOUNT
                user_name = "SYSTEM"
                password = None
            else:
                if password:
                    logon_type = TASK_LOGON_PASSWORD
                else:
                    logon_type = TASK_LOGON_INTERACTIVE_TOKEN
        else:
            password = None
            logon_type = TASK_LOGON_NONE

        # Save the task
        try:
            task_folder.RegisterTask(
                name, xml_text, TASK_CREATE, user_name, password, logon_type
            )

        except pythoncom.com_error as error:
            hr, msg, exc, arg = error.args  # pylint: disable=W0633
            error_code = _signed_to_unsigned_int32(exc[5])
            fc = {
                0x80041319: "Required element or attribute missing",
                0x80041318: "Value incorrectly formatted or out of range",
                0x80020005: "Access denied",
                0x80041309: "A task's trigger is not found",
                0x8004130A: (
                    "One or more of the properties required to run this "
                    "task have not been set"
                ),
                0x8004130C: (
                    "The Task Scheduler service is not installed on this computer"
                ),
                0x8004130D: "The task object could not be opened",
                0x8004130E: (
                    "The object is either an invalid task object or is not "
                    "a task object"
                ),
                0x8004130F: (
                    "No account information could be found in the Task "
                    "Scheduler security database for the task indicated"
                ),
                0x80041310: "Unable to establish existence of the account specified",
                0x80041311: (
                    "Corruption was detected in the Task Scheduler "
                    "security database; the database has been reset"
                ),
                0x80041313: "The task object version is either unsupported or invalid",
                0x80041314: (
                    "The task has been configured with an unsupported "
                    "combination of account settings and run time options"
                ),
                0x80041315: "The Task Scheduler Service is not running",
                0x80041316: "The task XML contains an unexpected node",
                0x80041317: (
                    "The task XML contains an element or attribute from an "
                    "unexpected namespace"
                ),
                0x8004131A: "The task XML is malformed",
                0x0004131C: (
                    "The task is registered, but may fail to start. Batch "
                    "logon privilege needs to be enabled for the task principal"
                ),
                0x8004131D: "The task XML contains too many nodes of the same type",
            }
            try:
                failure_code = fc[error_code]
            except KeyError:
                failure_code = f"Unknown Failure: {hex(error_code)}"
            finally:
                log.debug("Failed to create task: %s", failure_code)
            raise CommandExecutionError(failure_code)

    # Verify creation
    return name in list_tasks(location)


def create_folder(name, location="\\"):
    r"""
    Create a folder in which to create tasks.

    Args:

        name (str):
            The name of the folder. This will be displayed in the task
            scheduler.

        location (str):
            A string value representing the location in which to create the
            folder. Default is ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' task.create_folder <folder_name>
    """
    # Check for existing folder
    if name in list_folders(location):
        # Connect to an existing task definition
        return f"{name} already exists"

    # Create the task service object
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # Get the folder to list folders from
        task_folder = task_service.GetFolder(location)
        task_folder.CreateFolder(name)

    # Verify creation
    return name in list_folders(location)


def edit_task(
    name=None,
    location="\\",
    # General Tab
    user_name=None,
    password=None,
    description=None,
    enabled=None,
    hidden=None,
    # Conditions Tab
    run_if_idle=None,
    idle_duration=None,
    idle_wait_timeout=None,
    idle_stop_on_end=None,
    idle_restart=None,
    ac_only=None,
    stop_if_on_batteries=None,
    wake_to_run=None,
    run_if_network=None,
    network_id=None,
    network_name=None,
    # Settings Tab
    allow_demand_start=None,
    start_when_available=None,
    restart_every=None,
    restart_count=3,
    execution_time_limit=None,
    force_stop=None,
    delete_after=None,
    multiple_instances=None,
    **kwargs,
):
    r"""
    Edit the parameters of a task. Triggers and Actions cannot be edited yet.

    Args:

        name (str):
            The name of the task. This will be displayed in the task scheduler.

        location (str):
            A string value representing the location in which to create the
            task. Default is ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

        user_name (str):
            The user account under which to run the task. To specify the
            'System' account, use 'System'. The password will be ignored.

        password (str):
            The password to use for authentication. This should set the task to
            run whether the user is logged in or not, but is currently not
            working.

            .. note::

                The combination of user_name and password determine how the
                task runs. For example, if a username is passed without at
                password the task will only run when the user is logged in. If a
                password is passed as well the task will run whether the user is
                logged on or not. If you pass 'System' as the username the task
                will run as the system account (the password parameter is
                ignored).

        description (str):
            A string representing the text that will be displayed in the
            description field in the task scheduler.

        enabled (bool):
            A boolean value representing whether or not the task is enabled.

        hidden (bool):
            A boolean value representing whether or not the task is hidden.

        run_if_idle (bool):
            Boolean value that indicates that the Task Scheduler will run the
            task only if the computer is in an idle state.

        idle_duration (str):
            A value that indicates the amount of time that the computer must be
            in an idle state before the task is run. Valid values are:

                - 1 minute
                - 5 minutes
                - 10 minutes
                - 15 minutes
                - 30 minutes
                - 1 hour

        idle_wait_timeout (str):
            A value that indicates the amount of time that the Task Scheduler
            will wait for an idle condition to occur. Valid values are:

                - Do not wait
                - 1 minute
                - 5 minutes
                - 10 minutes
                - 15 minutes
                - 30 minutes
                - 1 hour
                - 2 hours

        idle_stop_on_end (bool):
            Boolean value that indicates that the Task Scheduler will terminate
            the task if the idle condition ends before the task is completed.

        idle_restart (bool):
            Boolean value that indicates whether the task is restarted when the
            computer cycles into an idle condition more than once.

        ac_only (bool):
            Boolean value that indicates that the Task Scheduler will launch the
            task only while on AC power.

        stop_if_on_batteries (bool):
            Boolean value that indicates that the task will be stopped if the
            computer begins to run on battery power.

        wake_to_run (bool):
            Boolean value that indicates that the Task Scheduler will wake the
            computer when it is time to run the task.

        run_if_network (bool):
            Boolean value that indicates that the Task Scheduler will run the
            task only when a network is available.

        network_id (guid):
            GUID value that identifies a network profile.

        network_name (str):
            Sets the name of a network profile. The name is used for display
            purposes.

        allow_demand_start (bool):
            Boolean value that indicates that the task can be started by using
            either the Run command or the Context menu.

        start_when_available (bool):
            Boolean value that indicates that the Task Scheduler can start the
            task at any time after its scheduled time has passed.

        restart_every (str):
            A value that specifies the interval between task restart attempts.
            Valid values are:

                - False (to disable)
                - 1 minute
                - 5 minutes
                - 10 minutes
                - 15 minutes
                - 30 minutes
                - 1 hour
                - 2 hours

        restart_count (int):
            The number of times the Task Scheduler will attempt to restart the
            task. Valid values are integers 1 - 999.

        execution_time_limit (bool, str):
            The amount of time allowed to complete the task. Valid values are:

                - False (to disable)
                - 1 hour
                - 2 hours
                - 4 hours
                - 8 hours
                - 12 hours
                - 1 day
                - 3 days

        force_stop (bool):
            Boolean value that indicates that the task may be terminated by
            using TerminateProcess.

        delete_after (bool, str):
            The amount of time that the Task Scheduler will wait before deleting
            the task after it expires. Requires a trigger with an expiration
            date. Valid values are:

                - False (to disable)
                - Immediately
                - 30 days
                - 90 days
                - 180 days
                - 365 days

        multiple_instances (str):
            Sets the policy that defines how the Task Scheduler deals with
            multiple instances of the task. Valid values are:

                - Parallel
                - Queue
                - No New Instance
                - Stop Existing

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt '*' task.edit_task <task_name> description='This task is awesome'
    """
    # TODO: Add more detailed return for items changed

    with salt.utils.winapi.Com():
        # Check for passed task_definition
        # If not passed, open a task definition for an existing task
        save_definition = False
        if kwargs.get("task_definition", False):
            task_definition = kwargs.get("task_definition")
        else:
            save_definition = True

            # Make sure a name was passed
            if not name:
                return 'Required parameter "name" not passed'

            # Make sure task exists to modify
            if name in list_tasks(location):

                # Connect to the task scheduler
                task_service = win32com.client.Dispatch("Schedule.Service")
                task_service.Connect()

                # get the folder to create the task in
                task_folder = task_service.GetFolder(location)

                # Connect to an existing task definition
                task_definition = task_folder.GetTask(name).Definition

            else:
                # Not found and create_new not set, return not found
                return f"{name} not found"

        # General Information
        if save_definition:
            task_definition.RegistrationInfo.Author = "Salt Minion"
            task_definition.RegistrationInfo.Source = "Salt Minion Daemon"

        if description is not None:
            task_definition.RegistrationInfo.Description = description

        # General Information: Security Options
        if user_name:
            # Determine logon type
            if user_name.lower() == "system":
                logon_type = TASK_LOGON_SERVICE_ACCOUNT
                user_name = "SYSTEM"
                password = None
            else:
                task_definition.Principal.Id = user_name
                if password:
                    logon_type = TASK_LOGON_PASSWORD
                else:
                    logon_type = TASK_LOGON_INTERACTIVE_TOKEN

            task_definition.Principal.UserID = user_name
            task_definition.Principal.DisplayName = user_name
            task_definition.Principal.LogonType = logon_type
            task_definition.Principal.RunLevel = TASK_RUNLEVEL_HIGHEST
        else:
            user_name = None
            password = None

        # Settings
        # https://msdn.microsoft.com/en-us/library/windows/desktop/aa383480(v=vs.85).aspx
        if enabled is not None:
            task_definition.Settings.Enabled = enabled
        # Settings: General Tab
        if hidden is not None:
            task_definition.Settings.Hidden = hidden

        # Settings: Conditions Tab (Idle)
        # https://msdn.microsoft.com/en-us/library/windows/desktop/aa380669(v=vs.85).aspx
        if run_if_idle is not None:
            task_definition.Settings.RunOnlyIfIdle = run_if_idle

        if task_definition.Settings.RunOnlyIfIdle:
            if idle_stop_on_end is not None:
                task_definition.Settings.IdleSettings.StopOnIdleEnd = idle_stop_on_end
            if idle_restart is not None:
                task_definition.Settings.IdleSettings.RestartOnIdle = idle_restart
            if idle_duration is not None:
                if idle_duration in duration:
                    task_definition.Settings.IdleSettings.IdleDuration = _lookup_first(
                        duration, idle_duration
                    )
                else:
                    return 'Invalid value for "idle_duration"'
            if idle_wait_timeout is not None:
                if idle_wait_timeout in duration:
                    task_definition.Settings.IdleSettings.WaitTimeout = _lookup_first(
                        duration, idle_wait_timeout
                    )
                else:
                    return 'Invalid value for "idle_wait_timeout"'

        # Settings: Conditions Tab (Power)
        if ac_only is not None:
            task_definition.Settings.DisallowStartIfOnBatteries = ac_only
        if stop_if_on_batteries is not None:
            task_definition.Settings.StopIfGoingOnBatteries = stop_if_on_batteries
        if wake_to_run is not None:
            task_definition.Settings.WakeToRun = wake_to_run

        # Settings: Conditions Tab (Network)
        # https://msdn.microsoft.com/en-us/library/windows/desktop/aa382067(v=vs.85).aspx
        if run_if_network is not None:
            task_definition.Settings.RunOnlyIfNetworkAvailable = run_if_network
        if task_definition.Settings.RunOnlyIfNetworkAvailable:
            if network_id:
                task_definition.Settings.NetworkSettings.Id = network_id
            if network_name:
                task_definition.Settings.NetworkSettings.Name = network_name

        # Settings: Settings Tab
        if allow_demand_start is not None:
            task_definition.Settings.AllowDemandStart = allow_demand_start
        if start_when_available is not None:
            task_definition.Settings.StartWhenAvailable = start_when_available
        if restart_every is not None:
            if restart_every is False:
                task_definition.Settings.RestartInterval = ""
            else:
                if restart_every in duration:
                    task_definition.Settings.RestartInterval = _lookup_first(
                        duration, restart_every
                    )
                else:
                    return 'Invalid value for "restart_every"'
        if task_definition.Settings.RestartInterval:
            if restart_count is not None:
                if restart_count in range(1, 999):
                    task_definition.Settings.RestartCount = restart_count
                else:
                    return '"restart_count" must be a value between 1 and 999'
        if execution_time_limit is not None:
            if execution_time_limit is False:
                task_definition.Settings.ExecutionTimeLimit = "PT0S"
            else:
                if execution_time_limit in duration:
                    task_definition.Settings.ExecutionTimeLimit = _lookup_first(
                        duration, execution_time_limit
                    )
                else:
                    return 'Invalid value for "execution_time_limit"'
        if force_stop is not None:
            task_definition.Settings.AllowHardTerminate = force_stop
        if delete_after is not None:
            # TODO: Check triggers for end_boundary
            if delete_after is False:
                task_definition.Settings.DeleteExpiredTaskAfter = ""
            else:
                if delete_after in duration:
                    task_definition.Settings.DeleteExpiredTaskAfter = _lookup_first(
                        duration, delete_after
                    )
                else:
                    return 'Invalid value for "delete_after"'
        if multiple_instances is not None:
            task_definition.Settings.MultipleInstances = instances[multiple_instances]

        # Save the task
        if save_definition:
            # Save the Changes
            return _save_task_definition(
                name=name,
                task_folder=task_folder,
                task_definition=task_definition,
                user_name=user_name,
                password=password,
                logon_type=task_definition.Principal.LogonType,
            )


def delete_task(name, location="\\"):
    r"""
    Delete a task from the task scheduler.

    Args:
        name (str):
            The name of the task to delete.

        location (str):
            A string value representing the location of the task. Default is
            ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' task.delete_task <task_name>
    """
    # Check for existing task
    if name not in list_tasks(location):
        return f"{name} not found in {location}"

    # connect to the task scheduler
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # get the folder to delete the task from
        task_folder = task_service.GetFolder(location)

        task_folder.DeleteTask(name, 0)

    # Verify deletion
    return name not in list_tasks(location)


def delete_folder(name, location="\\"):
    r"""
    Delete a folder from the task scheduler.

    Args:

        name (str):
            The name of the folder to delete.

        location (str):
            A string value representing the location of the folder.  Default is
            ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' task.delete_folder <folder_name>
    """
    # Check for existing folder
    if name not in list_folders(location):
        return f"{name} not found in {location}"

    # connect to the task scheduler
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # get the folder to delete the folder from
        task_folder = task_service.GetFolder(location)

        # Delete the folder
        task_folder.DeleteFolder(name, 0)

    # Verify deletion
    return name not in list_folders(location)


def run(name, location="\\"):
    r"""
    Run a scheduled task manually.

    Args:

        name (str):
            The name of the task to run.

        location (str):
            A string value representing the location of the task. Default is
            ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' task.run <task_name>
    """
    # Check for existing folder
    if name not in list_tasks(location):
        return f"{name} not found in {location}"

    # connect to the task scheduler
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # get the folder to delete the folder from
        task_folder = task_service.GetFolder(location)
        task = task_folder.GetTask(name)

        try:
            task.Run("")
            return True
        except pythoncom.com_error:
            return False


def run_wait(name, location="\\"):
    r"""
    Run a scheduled task and return when the task finishes

    Args:

        name (str):
            The name of the task to run.

        location (str):
            A string value representing the location of the task. Default is
            ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' task.run_wait <task_name>
    """
    # Check for existing folder
    if name not in list_tasks(location):
        return f"{name} not found in {location}"

    # connect to the task scheduler
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # get the folder to delete the folder from
        task_folder = task_service.GetFolder(location)
        task = task_folder.GetTask(name)

        # Is the task already running
        if task.State == TASK_STATE_RUNNING:
            return "Task already running"

        try:
            task.Run("")
            time.sleep(1)
            running = True
        except pythoncom.com_error:
            return False

        while running:
            running = False
            try:
                running_tasks = task_service.GetRunningTasks(0)
                if running_tasks.Count:
                    for item in running_tasks:
                        if item.Name == name:
                            running = True
            except pythoncom.com_error:
                running = False

    return True


def stop(name, location="\\"):
    r"""
    Stop a scheduled task.

    Args:

        name (str):
            The name of the task to stop.

        location (str):
            A string value representing the location of the task. Default is
            ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' task.list_stop <task_name>
    """
    # Check for existing folder
    if name not in list_tasks(location):
        return f"{name} not found in {location}"

    # connect to the task scheduler
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # get the folder to delete the folder from
        task_folder = task_service.GetFolder(location)
        task = task_folder.GetTask(name)

        try:
            task.Stop(0)
            return True
        except pythoncom.com_error:
            return False


def status(name, location="\\"):
    r"""
    Determine the status of a task. Is it Running, Queued, Ready, etc.

    Args:

        name (str):
            The name of the task for which to return the status

        location (str):
            A string value representing the location of the task. Default is
            ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

    Returns:
        str: The current status of the task. Will be one of the following:

            - Unknown
            - Disabled
            - Queued
            - Ready
            - Running

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' task.list_status <task_name>
    """
    # Check for existing folder
    if name not in list_tasks(location):
        return f"{name} not found in {location}"

    # connect to the task scheduler
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # get the folder where the task is defined
        task_folder = task_service.GetFolder(location)
        task = task_folder.GetTask(name)

        return states[task.State]


def info(name, location="\\"):
    r"""
    Get the details about a task in the task scheduler.

    Args:

        name (str):
            The name of the task for which to return the status

        location (str):
            A string value representing the location of the task. Default is
            ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

    Returns:
        dict: A dictionary containing the task configuration

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' task.info <task_name>
    """
    # Check for existing folder
    if name not in list_tasks(location):
        return f"{name} not found in {location}"

    # connect to the task scheduler
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # get the folder to delete the folder from
        task_folder = task_service.GetFolder(location)
        task = task_folder.GetTask(name)

        last_task_result_code = _signed_to_unsigned_int32(task.LastTaskResult)
        try:
            last_task_result = results[last_task_result_code]
        except KeyError:
            last_task_result = f"Unknown Task Result: {hex(last_task_result_code)}"

        properties = {
            "enabled": task.Enabled,
            "last_run": _get_date_value(task.LastRunTime),
            "last_run_result": last_task_result,
            "missed_runs": task.NumberOfMissedRuns,
            "next_run": _get_date_value(task.NextRunTime),
            "status": states[task.State],
        }

        def_set = task.Definition.Settings

        settings = {
            "allow_demand_start": def_set.AllowDemandStart,
            "force_stop": def_set.AllowHardTerminate,
        }

        if def_set.DeleteExpiredTaskAfter == "":
            settings["delete_after"] = False
        elif def_set.DeleteExpiredTaskAfter == "PT0S":
            settings["delete_after"] = "Immediately"
        else:
            settings["delete_after"] = _reverse_lookup(
                duration, def_set.DeleteExpiredTaskAfter
            )

        if def_set.ExecutionTimeLimit == "" or def_set.ExecutionTimeLimit == "PT0S":
            settings["execution_time_limit"] = False
        else:
            settings["execution_time_limit"] = _reverse_lookup(
                duration, def_set.ExecutionTimeLimit
            )

        settings["multiple_instances"] = _reverse_lookup(
            instances, def_set.MultipleInstances
        )

        if def_set.RestartInterval == "":
            settings["restart_interval"] = False
        else:
            settings["restart_interval"] = _reverse_lookup(
                duration, def_set.RestartInterval
            )

        if settings["restart_interval"]:
            settings["restart_count"] = def_set.RestartCount
        settings["stop_if_on_batteries"] = def_set.StopIfGoingOnBatteries
        settings["wake_to_run"] = def_set.WakeToRun

        conditions = {
            "ac_only": def_set.DisallowStartIfOnBatteries,
            "run_if_idle": def_set.RunOnlyIfIdle,
            "run_if_network": def_set.RunOnlyIfNetworkAvailable,
            "start_when_available": def_set.StartWhenAvailable,
        }

        if conditions["run_if_idle"]:
            idle_set = def_set.IdleSettings
            conditions["idle_duration"] = idle_set.IdleDuration
            conditions["idle_restart"] = idle_set.RestartOnIdle
            conditions["idle_stop_on_end"] = idle_set.StopOnIdleEnd
            conditions["idle_wait_timeout"] = idle_set.WaitTimeout

        if conditions["run_if_network"]:
            net_set = def_set.NetworkSettings
            conditions["network_id"] = net_set.Id
            conditions["network_name"] = net_set.Name

        actions = []
        for actionObj in task.Definition.Actions:
            action = {"action_type": _reverse_lookup(action_types, actionObj.Type)}
            if actionObj.Path:
                action["cmd"] = actionObj.Path
            if actionObj.Arguments:
                action["arguments"] = actionObj.Arguments
            if actionObj.WorkingDirectory:
                action["working_dir"] = actionObj.WorkingDirectory
            actions.append(action)

        triggers = []
        for triggerObj in task.Definition.Triggers:
            trigger = {"trigger_type": _reverse_lookup(trigger_types, triggerObj.Type)}
            if triggerObj.ExecutionTimeLimit:
                trigger["execution_time_limit"] = _reverse_lookup(
                    duration, triggerObj.ExecutionTimeLimit
                )
            if triggerObj.StartBoundary:
                start_date, start_time = triggerObj.StartBoundary.split("T", 1)
                trigger["start_date"] = start_date
                trigger["start_time"] = start_time
            if triggerObj.EndBoundary:
                end_date, end_time = triggerObj.EndBoundary.split("T", 1)
                trigger["end_date"] = end_date
                trigger["end_time"] = end_time
            trigger["enabled"] = triggerObj.Enabled
            if hasattr(triggerObj, "RandomDelay"):
                if triggerObj.RandomDelay:
                    trigger["random_delay"] = _reverse_lookup(
                        duration, triggerObj.RandomDelay
                    )
                else:
                    trigger["random_delay"] = False
            if hasattr(triggerObj, "Delay"):
                if triggerObj.Delay:
                    trigger["delay"] = _reverse_lookup(duration, triggerObj.Delay)
                else:
                    trigger["delay"] = False
            if hasattr(triggerObj, "Repetition"):
                trigger["repeat_duration"] = _reverse_lookup(
                    duration, triggerObj.Repetition.Duration
                )
                trigger["repeat_interval"] = _reverse_lookup(
                    duration, triggerObj.Repetition.Interval
                )
                trigger["repeat_stop_at_duration_end"] = (
                    triggerObj.Repetition.StopAtDurationEnd
                )
            triggers.append(trigger)

        properties["settings"] = settings
        properties["conditions"] = conditions
        properties["actions"] = actions
        properties["triggers"] = triggers
        ret = properties

    return ret


def add_action(name=None, location="\\", action_type="Execute", **kwargs):
    r"""
    Add an action to a task.

    Args:

        name (str):
            The name of the task to which to add the action.

        location (str):
            A string value representing the location of the task. Default is
            ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

        action_type (str):
            The type of action to add. There are three action types. Each one
            requires its own set of Keyword Arguments (kwargs). Valid values
            are:

                - Execute
                - Email
                - Message

    Required arguments for each action_type:

    **Execute**

        Execute a command or an executable

            cmd (str):
                (required) The command or executable to run.

            arguments (str):
                (optional) Arguments to be passed to the command or executable.
                To launch a script the first command will need to be the
                interpreter for the script. For example, to run a vbscript you
                would pass ``cscript.exe`` in the ``cmd`` parameter and pass the
                script in the ``arguments`` parameter as follows:

                    - ``cmd='cscript.exe' arguments='c:\scripts\myscript.vbs'``

                Batch files do not need an interpreter and may be passed to the
                cmd parameter directly.

            start_in (str):
                (optional) The current working directory for the command.

    **Email**

        Send and email. Requires ``server``, ``from``, and ``to`` or ``cc``.

            from (str): The sender

            reply_to (str): Who to reply to

            to (str): The recipient

            cc (str): The CC recipient

            bcc (str): The BCC recipient

            subject (str): The subject of the email

            body (str): The Message Body of the email

            server (str): The server used to send the email

            attachments (list):
                A list of attachments. These will be the paths to the files to
                attach. ie: ``attachments="['C:\attachment1.txt',
                'C:\attachment2.txt']"``

    **Message**

        Display a dialog box. The task must be set to "Run only when user is
        logged on" in order for the dialog box to display. Both parameters are
        required.

            title (str):
                The dialog box title.

            message (str):
                The dialog box message body

    Returns:
        dict: A dictionary containing the task configuration

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' task.add_action <task_name> cmd='del /Q /S C:\\Temp'
    """
    with salt.utils.winapi.Com():
        save_definition = False
        if kwargs.get("task_definition", False):
            task_definition = kwargs.get("task_definition")
        else:
            save_definition = True
            # Make sure a name was passed
            if not name:
                return 'Required parameter "name" not passed'

            # Make sure task exists
            if name in list_tasks(location):

                # Connect to the task scheduler
                task_service = win32com.client.Dispatch("Schedule.Service")
                task_service.Connect()

                # get the folder to create the task in
                task_folder = task_service.GetFolder(location)

                # Connect to an existing task definition
                task_definition = task_folder.GetTask(name).Definition

            else:
                # Not found and create_new not set, return not found
                return f"{name} not found"

        # Action Settings
        task_action = task_definition.Actions.Create(action_types[action_type])
        if action_types[action_type] == TASK_ACTION_EXEC:
            task_action.Id = "Execute_ID1"
            if kwargs.get("cmd", False):
                task_action.Path = kwargs.get("cmd")
            else:
                return 'Required parameter "cmd" not found'
            task_action.Arguments = kwargs.get("arguments", "")
            task_action.WorkingDirectory = kwargs.get("start_in", "")

        elif action_types[action_type] == TASK_ACTION_SEND_EMAIL:
            task_action.Id = "Email_ID1"

            # Required Parameters
            if kwargs.get("server", False):
                task_action.Server = kwargs.get("server")
            else:
                return 'Required parameter "server" not found'

            if kwargs.get("from", False):
                task_action.From = kwargs.get("from")
            else:
                return 'Required parameter "from" not found'

            if kwargs.get("to", False) or kwargs.get("cc", False):
                if kwargs.get("to"):
                    task_action.To = kwargs.get("to")
                if kwargs.get("cc"):
                    task_action.Cc = kwargs.get("cc")
            else:
                return 'Required parameter "to" or "cc" not found'

            # Optional Parameters
            if kwargs.get("reply_to"):
                task_action.ReplyTo = kwargs.get("reply_to")
            if kwargs.get("bcc"):
                task_action.Bcc = kwargs.get("bcc")
            if kwargs.get("subject"):
                task_action.Subject = kwargs.get("subject")
            if kwargs.get("body"):
                task_action.Body = kwargs.get("body")
            if kwargs.get("attachments"):
                task_action.Attachments = kwargs.get("attachments")

        elif action_types[action_type] == TASK_ACTION_SHOW_MESSAGE:
            task_action.Id = "Message_ID1"

            if kwargs.get("title", False):
                task_action.Title = kwargs.get("title")
            else:
                return 'Required parameter "title" not found'

            if kwargs.get("message", False):
                task_action.MessageBody = kwargs.get("message")
            else:
                return 'Required parameter "message" not found'

        # Save the task
        if save_definition:
            # Save the Changes
            return _save_task_definition(
                name=name,
                task_folder=task_folder,
                task_definition=task_definition,
                user_name=task_definition.Principal.UserID,
                password=None,
                logon_type=task_definition.Principal.LogonType,
            )


def _clear_actions(name, location="\\"):
    r"""
    Remove all actions from the task.

    :param str name: The name of the task from which to clear all actions.

    :param str location: A string value representing the location of the task.
    Default is ``\`` which is the root for the task scheduler
    (``C:\Windows\System32\tasks``).

    :return: True if successful, False if unsuccessful
    :rtype: bool
    """
    # TODO: The problem is, you have to have at least one action for the task to
    # TODO: be valid, so this will always fail with a 'Required element or
    # TODO: attribute missing' error.
    # TODO: Make this an internal function that clears the functions but doesn't
    # TODO: save it. Then you can add a new function. Maybe for editing an
    # TODO: action.
    # Check for existing task
    if name not in list_tasks(location):
        return f"{name} not found in {location}"

    # Create the task service object
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # Get the actions from the task
        task_folder = task_service.GetFolder(location)
        task_definition = task_folder.GetTask(name).Definition
        actions = task_definition.Actions

        actions.Clear()

        # Save the Changes
        return _save_task_definition(
            name=name,
            task_folder=task_folder,
            task_definition=task_definition,
            user_name=task_definition.Principal.UserID,
            password=None,
            logon_type=task_definition.Principal.LogonType,
        )


def add_trigger(
    name=None,
    location="\\",
    trigger_type=None,
    trigger_enabled=True,
    start_date=None,
    start_time=None,
    end_date=None,
    end_time=None,
    random_delay=None,
    repeat_interval=None,
    repeat_duration=None,
    repeat_stop_at_duration_end=False,
    execution_time_limit=None,
    delay=None,
    **kwargs,
):
    r"""
    Add a trigger to a Windows Scheduled task

    .. note::

        Arguments are parsed by the YAML loader and are subject to
        yaml's idiosyncrasies. Therefore, time values in some
        formats (``%H:%M:%S`` and ``%H:%M``) should to be quoted.
        See `YAML IDIOSYNCRASIES`_ for more details.

    .. _`YAML IDIOSYNCRASIES`: https://docs.saltproject.io/en/latest/topics/troubleshooting/yaml_idiosyncrasies.html#time-expressions

    Args:

        name (str):
            The name of the task to which to add the trigger.

        location (str):
            A string value representing the location of the task. Default is
            ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

        trigger_type (str):
            The type of trigger to create. This is defined when the trigger is
            created and cannot be changed later. Options are as follows:

                - Event
                - Once
                - Daily
                - Weekly
                - Monthly
                - MonthlyDay
                - OnIdle
                - OnTaskCreation
                - OnBoot
                - OnLogon
                - OnSessionChange

        trigger_enabled (bool):
            Boolean value that indicates whether the trigger is enabled.

        start_date (str):
            The date when the trigger is activated. If no value is passed, the
            current date will be used. Can be one of the following formats:

                - %Y-%m-%d
                - %m-%d-%y
                - %m-%d-%Y
                - %m/%d/%y
                - %m/%d/%Y
                - %Y/%m/%d

        start_time (str):
            The time when the trigger is activated. If no value is passed,
            midnight will be used. Can be one of the following formats:

                - %I:%M:%S %p
                - %I:%M %p
                - %H:%M:%S
                - %H:%M

        end_date (str):
            The date when the trigger is deactivated. The trigger cannot start
            the task after it is deactivated. Can be one of the following
            formats:

                - %Y-%m-%d
                - %m-%d-%y
                - %m-%d-%Y
                - %m/%d/%y
                - %m/%d/%Y
                - %Y/%m/%d

        end_time (str):
            The time when the trigger is deactivated. If this is not passed
            with ``end_date`` it will be set to midnight. Can be one of the
            following formats:

                - %I:%M:%S %p
                - %I:%M %p
                - %H:%M:%S
                - %H:%M

        random_delay (str):
            The delay time that is randomly added to the start time of the
            trigger. Valid values are:

                - 30 seconds
                - 1 minute
                - 30 minutes
                - 1 hour
                - 8 hours
                - 1 day

            .. note::

                This parameter applies to the following trigger types

                    - Once
                    - Daily
                    - Weekly
                    - Monthly
                    - MonthlyDay

        repeat_interval (str):
            The amount of time between each restart of the task. Valid values
            are:

                - 5 minutes
                - 10 minutes
                - 15 minutes
                - 30 minutes
                - 1 hour

        repeat_duration (str):
            How long the pattern is repeated. Valid values are:

                - Indefinitely
                - 15 minutes
                - 30 minutes
                - 1 hour
                - 12 hours
                - 1 day

        repeat_stop_at_duration_end (bool):
            Boolean value that indicates if a running instance of the task is
            stopped at the end of the repetition pattern duration.

        execution_time_limit (str):
            The maximum amount of time that the task launched by the trigger is
            allowed to run. Valid values are:

                - 30 minutes
                - 1 hour
                - 2 hours
                - 4 hours
                - 8 hours
                - 12 hours
                - 1 day
                - 3 days (default)

        delay (str):
            The time the trigger waits after its activation to start the task.
            Valid values are:

                - 15 seconds
                - 30 seconds
                - 1 minute
                - 30 minutes
                - 1 hour
                - 8 hours
                - 1 day

            .. note::

                This parameter applies to the following trigger types:

                    - OnLogon
                    - OnBoot
                    - Event
                    - OnTaskCreation
                    - OnSessionChange

    **kwargs**

    There are optional keyword arguments determined by the type of trigger
    being defined. They are as follows:

    *Event*

        The trigger will be fired by an event.

            subscription (str):
                An event definition in xml format that fires the trigger. The
                easiest way to get this would is to create an event in Windows
                Task Scheduler and then copy the xml text.

    *Once*

        No special parameters required.

    *Daily*

        The task will run daily.

            days_interval (int):
                The interval between days in the schedule. An interval of 1
                produces a daily schedule. An interval of 2 produces an
                every-other day schedule. If no interval is specified, 1 is
                used. Valid entries are 1 - 999.

    *Weekly*

        The task will run weekly.

            weeks_interval (int):
                The interval between weeks in the schedule. An interval of 1
                produces a weekly schedule. An interval of 2 produces an
                every-other week schedule. If no interval is specified, 1 is
                used. Valid entries are 1 - 52.

            days_of_week (list):
                Sets the days of the week on which the task runs. Should be a
                list. ie: ``['Monday','Wednesday','Friday']``. Valid entries are
                the names of the days of the week.

    *Monthly*

        The task will run monthly.

            months_of_year (list):
                Sets the months of the year during which the task runs. Should
                be a list. ie: ``['January','July']``. Valid entries are the
                full names of all the months.

            days_of_month (list):
                Sets the days of the month during which the task runs. Should be
                a list. ie: ``[1, 15, 'Last']``. Options are all days of the
                month 1 - 31 and the word 'Last' to indicate the last day of the
                month.

            last_day_of_month (bool):
                Boolean value that indicates that the task runs on the last day
                of the month regardless of the actual date of that day.

                .. note::

                    You can set the task to run on the last day of the month by
                    either including the word 'Last' in the list of days, or
                    setting the parameter 'last_day_of_month' equal to ``True``.

    *MonthlyDay*

        The task will run monthly on the specified day.

            months_of_year (list):
                Sets the months of the year during which the task runs. Should
                be a list. ie: ``['January','July']``. Valid entries are the
                full names of all the months.

            weeks_of_month (list):
                Sets the weeks of the month during which the task runs. Should
                be a list. ie: ``['First','Third']``. Valid options are:

                    - First
                    - Second
                    - Third
                    - Fourth

            last_week_of_month (bool):
                Boolean value that indicates that the task runs on the last week
                of the month.

            days_of_week (list):
                Sets the days of the week during which the task runs. Should be
                a list. ie: ``['Monday','Wednesday','Friday']``.  Valid entries
                are the names of the days of the week.

    *OnIdle*

        No special parameters required.

    *OnTaskCreation*

        No special parameters required.

    *OnBoot*

        No special parameters required.

    *OnLogon*

        No special parameters required.

    *OnSessionChange*

        The task will be triggered by a session change.

            session_user_name (str):
                Sets the user for the Terminal Server session. When a session
                state change is detected for this user, a task is started. To
                detect session status change for any user, do not pass this
                parameter.

            state_change (str):
                Sets the kind of Terminal Server session change that would
                trigger a task launch. Valid options are:

                    - ConsoleConnect: When you connect to a user session (switch
                      users)
                    - ConsoleDisconnect: When you disconnect a user session
                      (switch users)
                    - RemoteConnect: When a user connects via Remote Desktop
                    - RemoteDisconnect: When a user disconnects via Remote
                      Desktop
                    - SessionLock: When the workstation is locked
                    - SessionUnlock: When the workstation is unlocked

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' task.add_trigger <task_name> trigger_type=Once trigger_enabled=True start_date=2016/12/1 start_time='"12:01"'
    """
    if not trigger_type:
        return 'Required parameter "trigger_type" not specified'

    # Define lookup dictionaries
    state_changes = {
        "ConsoleConnect": 1,
        "ConsoleDisconnect": 2,
        "RemoteConnect": 3,
        "RemoteDisconnect": 4,
        "SessionLock": 7,
        "SessionUnlock": 8,
    }

    days = {
        1: 0x1,
        2: 0x2,
        3: 0x4,
        4: 0x8,
        5: 0x10,
        6: 0x20,
        7: 0x40,
        8: 0x80,
        9: 0x100,
        10: 0x200,
        11: 0x400,
        12: 0x800,
        13: 0x1000,
        14: 0x2000,
        15: 0x4000,
        16: 0x8000,
        17: 0x10000,
        18: 0x20000,
        19: 0x40000,
        20: 0x80000,
        21: 0x100000,
        22: 0x200000,
        23: 0x400000,
        24: 0x800000,
        25: 0x1000000,
        26: 0x2000000,
        27: 0x4000000,
        28: 0x8000000,
        29: 0x10000000,
        30: 0x20000000,
        31: 0x40000000,
        "Last": 0x80000000,
    }

    weekdays = {
        "Sunday": 0x1,
        "Monday": 0x2,
        "Tuesday": 0x4,
        "Wednesday": 0x8,
        "Thursday": 0x10,
        "Friday": 0x20,
        "Saturday": 0x40,
    }

    weeks = {"First": 0x1, "Second": 0x2, "Third": 0x4, "Fourth": 0x8}

    months = {
        "January": 0x1,
        "February": 0x2,
        "March": 0x4,
        "April": 0x8,
        "May": 0x10,
        "June": 0x20,
        "July": 0x40,
        "August": 0x80,
        "September": 0x100,
        "October": 0x200,
        "November": 0x400,
        "December": 0x800,
    }

    # Format Date Parameters
    if start_date:
        date_format = _get_date_time_format(start_date)
        if date_format:
            dt_obj = datetime.strptime(start_date, date_format)
        else:
            return "Invalid start_date"
    else:
        dt_obj = datetime.now()

    if start_time:
        time_format = _get_date_time_format(start_time)
        if time_format:
            tm_obj = datetime.strptime(start_time, time_format)
        else:
            return "Invalid start_time"
    else:
        tm_obj = datetime.strptime("00:00:00", "%H:%M:%S")

    start_boundary = "{}T{}".format(
        dt_obj.strftime("%Y-%m-%d"), tm_obj.strftime("%H:%M:%S")
    )

    dt_obj = None
    if end_date:
        date_format = _get_date_time_format(end_date)
        if date_format:
            dt_obj = datetime.strptime(end_date, date_format)
        else:
            return "Invalid end_date"

    if end_time:
        time_format = _get_date_time_format(end_time)
        if time_format:
            tm_obj = datetime.strptime(end_time, time_format)
        else:
            return "Invalid end_time"
    else:
        tm_obj = datetime.strptime("00:00:00", "%H:%M:%S")

    end_boundary = None
    if dt_obj and tm_obj:
        end_boundary = "{}T{}".format(
            dt_obj.strftime("%Y-%m-%d"), tm_obj.strftime("%H:%M:%S")
        )

    with salt.utils.winapi.Com():
        save_definition = False
        if kwargs.get("task_definition", False):
            task_definition = kwargs.get("task_definition")
        else:
            save_definition = True
            # Make sure a name was passed
            if not name:
                return 'Required parameter "name" not passed'

            # Make sure task exists
            if name in list_tasks(location):

                # Connect to the task scheduler
                task_service = win32com.client.Dispatch("Schedule.Service")
                task_service.Connect()

                # get the folder to create the task in
                task_folder = task_service.GetFolder(location)

                # Connect to an existing task definition
                task_definition = task_folder.GetTask(name).Definition

            else:
                # Not found and create_new not set, return not found
                return f"{name} not found"

        # Create a New Trigger
        trigger = task_definition.Triggers.Create(trigger_types[trigger_type])

        # Shared Trigger Parameters
        # Settings
        trigger.StartBoundary = start_boundary
        # Advanced Settings
        if delay:
            trigger.Delay = _lookup_first(duration, delay)
        if random_delay:
            trigger.RandomDelay = _lookup_first(duration, random_delay)
        if repeat_interval:
            trigger.Repetition.Interval = _lookup_first(duration, repeat_interval)
            if repeat_duration:
                trigger.Repetition.Duration = _lookup_first(duration, repeat_duration)
            trigger.Repetition.StopAtDurationEnd = repeat_stop_at_duration_end
        if execution_time_limit:
            trigger.ExecutionTimeLimit = _lookup_first(duration, execution_time_limit)
        if end_boundary:
            trigger.EndBoundary = end_boundary
        trigger.Enabled = trigger_enabled

        # Trigger Specific Parameters
        # Event Trigger Parameters
        if trigger_types[trigger_type] == TASK_TRIGGER_EVENT:
            # Check for required kwargs
            if kwargs.get("subscription", False):
                trigger.Id = "Event_ID1"
                trigger.Subscription = kwargs.get("subscription")
            else:
                return 'Required parameter "subscription" not passed'

        elif trigger_types[trigger_type] == TASK_TRIGGER_TIME:
            trigger.Id = "Once_ID1"

        # Daily Trigger Parameters
        elif trigger_types[trigger_type] == TASK_TRIGGER_DAILY:
            trigger.Id = "Daily_ID1"
            trigger.DaysInterval = kwargs.get("days_interval", 1)

        # Weekly Trigger Parameters
        elif trigger_types[trigger_type] == TASK_TRIGGER_WEEKLY:
            trigger.Id = "Weekly_ID1"
            trigger.WeeksInterval = kwargs.get("weeks_interval", 1)
            if kwargs.get("days_of_week", False):
                bits_days = 0
                for weekday in kwargs.get("days_of_week"):
                    bits_days |= weekdays[weekday]
                trigger.DaysOfWeek = bits_days
            else:
                return 'Required parameter "days_of_week" not passed'

        # Monthly Trigger Parameters
        elif trigger_types[trigger_type] == TASK_TRIGGER_MONTHLY:
            trigger.Id = "Monthly_ID1"
            if kwargs.get("months_of_year", False):
                bits_months = 0
                for month in kwargs.get("months_of_year"):
                    bits_months |= months[month]
                trigger.MonthsOfYear = bits_months
            else:
                return 'Required parameter "months_of_year" not passed'

            if kwargs.get("days_of_month", False) or kwargs.get(
                "last_day_of_month", False
            ):
                if kwargs.get("days_of_month", False):
                    bits_days = 0
                    for day in kwargs.get("days_of_month"):
                        bits_days |= days[day]
                    trigger.DaysOfMonth = bits_days
                trigger.RunOnLastDayOfMonth = kwargs.get("last_day_of_month", False)
            else:
                return (
                    'Monthly trigger requires "days_of_month" or "last_day_of_'
                    'month" parameters'
                )

        # Monthly Day Of Week Trigger Parameters
        elif trigger_types[trigger_type] == TASK_TRIGGER_MONTHLYDOW:
            trigger.Id = "Monthly_DOW_ID1"
            if kwargs.get("months_of_year", False):
                bits_months = 0
                for month in kwargs.get("months_of_year"):
                    bits_months |= months[month]
                trigger.MonthsOfYear = bits_months
            else:
                return 'Required parameter "months_of_year" not passed'

            if kwargs.get("weeks_of_month", False) or kwargs.get(
                "last_week_of_month", False
            ):
                if kwargs.get("weeks_of_month", False):
                    bits_weeks = 0
                    for week in kwargs.get("weeks_of_month"):
                        bits_weeks |= weeks[week]
                    trigger.WeeksOfMonth = bits_weeks
                trigger.RunOnLastWeekOfMonth = kwargs.get("last_week_of_month", False)
            else:
                return (
                    'Monthly DOW trigger requires "weeks_of_month" or "last_'
                    'week_of_month" parameters'
                )

            if kwargs.get("days_of_week", False):
                bits_days = 0
                for weekday in kwargs.get("days_of_week"):
                    bits_days |= weekdays[weekday]
                trigger.DaysOfWeek = bits_days
            else:
                return 'Required parameter "days_of_week" not passed'

        # On Idle Trigger Parameters
        elif trigger_types[trigger_type] == TASK_TRIGGER_IDLE:
            trigger.Id = "OnIdle_ID1"

        # On Task Creation Trigger Parameters
        elif trigger_types[trigger_type] == TASK_TRIGGER_REGISTRATION:
            trigger.Id = "OnTaskCreation_ID1"

        # On Boot Trigger Parameters
        elif trigger_types[trigger_type] == TASK_TRIGGER_BOOT:
            trigger.Id = "OnBoot_ID1"

        # On Logon Trigger Parameters
        elif trigger_types[trigger_type] == TASK_TRIGGER_LOGON:
            trigger.Id = "OnLogon_ID1"

        # On Session State Change Trigger Parameters
        elif trigger_types[trigger_type] == TASK_TRIGGER_SESSION_STATE_CHANGE:
            trigger.Id = "OnSessionStateChange_ID1"
            if kwargs.get("session_user_name", False):
                trigger.UserId = kwargs.get("session_user_name")
            if kwargs.get("state_change", False):
                trigger.StateChange = state_changes[kwargs.get("state_change")]
            else:
                return 'Required parameter "state_change" not passed'

        # Save the task
        if save_definition:
            # Save the Changes
            return _save_task_definition(
                name=name,
                task_folder=task_folder,
                task_definition=task_definition,
                user_name=task_definition.Principal.UserID,
                password=None,
                logon_type=task_definition.Principal.LogonType,
            )


def clear_triggers(name, location="\\"):
    r"""
    Remove all triggers from the task.

    Args:

        name (str):
            The name of the task from which to clear all triggers.

        location (str):
            A string value representing the location of the task. Default is
            ``\`` which is the root for the task scheduler
            (``C:\Windows\System32\tasks``).

    Returns:
        bool: ``True`` if successful, otherwise ``False``

    CLI Example:

    .. code-block:: bash

        salt 'minion-id' task.clear_trigger <task_name>
    """
    # Check for existing task
    if name not in list_tasks(location):
        return f"{name} not found in {location}"

    # Create the task service object
    with salt.utils.winapi.Com():
        task_service = win32com.client.Dispatch("Schedule.Service")
        task_service.Connect()

        # Get the triggers from the task
        task_folder = task_service.GetFolder(location)
        task_definition = task_folder.GetTask(name).Definition
        triggers = task_definition.Triggers

        triggers.Clear()

        # Save the Changes
        return _save_task_definition(
            name=name,
            task_folder=task_folder,
            task_definition=task_definition,
            user_name=task_definition.Principal.UserID,
            password=None,
            logon_type=task_definition.Principal.LogonType,
        )
