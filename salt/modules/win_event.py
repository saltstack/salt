"""
A module for working with the Windows Event log system.
.. versionadded:: 3006.0
"""
# https://docs.microsoft.com/en-us/windows/win32/eventlog/event-logging

import collections
import logging

import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

try:
    import pywintypes
    import win32evtlog
    import win32evtlogutil
    import winerror

    # Only windows needs this dependency at runtime
    import xmltodict

    IMPORT_STATUS = True
except ImportError:
    IMPORT_STATUS = False


log = logging.getLogger(__name__)
__virtualname__ = "win_event"


def __virtual__():
    """
    Load only on minions running on Windows.
    """

    if not salt.utils.platform.is_windows():
        return False, "win_event: Must be on Windows"
    if not IMPORT_STATUS:
        return False, "win_event: Missing PyWin32"
    return __virtualname__


def _to_bytes(data, encoding="utf-8", encode_keys=False):
    """
    Convert string objects to byte objects.

    .. warning::
        This function will destroy the data object and objects that data links
        to.

    Args:

        data (object): The string object to encode

        encoding(str): The encoding type

        encode_keys(bool): If false key strings will not be turned into bytes

    Returns:
        (object): An object with the new encoding
    """

    if isinstance(data, dict):
        new_dict = {}
        # recursively check every item in the dict
        for key in data:
            item = _to_bytes(data[key], encoding)
            if encode_keys:
                # keys that are strings most be made into bytes
                key = _to_bytes(key, encoding)
            new_dict[key] = item
        data = new_dict
    elif isinstance(data, list):
        new_list = []
        # recursively check every item in the list
        for item in data:
            new_list.append(_to_bytes(item, encoding))
        data = new_list
    elif isinstance(data, tuple):
        new_list = []
        # recursively check every item in the tuple
        for item in data:
            new_list.append(_to_bytes(item, encoding))
        data = tuple(new_list)
    elif isinstance(data, str):
        # encode string data to bytes
        data = data.encode(encoding)

    return data


def _raw_time(time):
    """
    Will make a pywintypes.datetime into a TimeTuple.

    Args:

        time (ob): A datetime object

    Returns:
        TimeTuple: A TimeTuple
    """
    TimeTuple = collections.namedtuple(
        "TimeTuple", "year, month, day, hour, minute, second"
    )

    return TimeTuple(
        time.year, time.month, time.day, time.hour, time.minute, time.second
    )


def _make_event_dict(event):
    """
    Will make a PyEventLogRecord into a dictionary

    Args:

        event (PyEventLogRecord): An event to convert to a dictionary

    Returns:
        dict: A dictionary containing the event information
    """
    # keys of all the parts of a Event supported by the API
    event_parts = (
        "closingRecordNumber",
        "computerName",
        "data",
        "eventCategory",
        "eventID",
        "eventType",
        "recordNumber",
        "reserved",
        "reservedFlags",
        "sid",
        "sourceName",
        "stringInserts",
        "timeGenerated",
        "timeWritten",
    )

    event_dict = {}
    for event_part in event_parts:
        # get object value and add it to the event dict
        event_dict[event_part] = getattr(
            event, event_part[0].upper() + event_part[1:], None
        )

    # format items
    event_dict["eventID"] = winerror.HRESULT_CODE(event_dict["eventID"])
    if event_dict["sid"] is not None:
        event_dict["sid"] = event_dict["sid"].GetSidIdentifierAuthority()
    event_dict["timeGenerated"] = _raw_time(event_dict["timeGenerated"])
    event_dict["timeWritten"] = _raw_time(event_dict["timeWritten"])

    return _to_bytes(event_dict)


def _get_handle(log_name):
    """
    Will try to open a PyHANDLE to the Event System

    Args:

        log_name (str): The name of the log to open

    Returns:
        PyHANDLE: A handle to the event log
    """

    # TODO: upgrade windows token
    # "log close" can fail if this is not done
    try:
        return win32evtlog.OpenEventLog(None, log_name)
    except pywintypes.error as exc:
        raise FileNotFoundError(
            "Failed to open log: {}\nError: {}".format(log_name, exc.strerror)
        )


def _close_handle(handle):
    """
    Will close the handle to the event log

    Args:

        handle (PyHANDLE): The handle to the event log to close
    """

    # TODO: downgrade windows token
    win32evtlog.CloseEventLog(handle)


def _event_generator(log_name):
    """
    Get all log events one by one. Events are not ordered

    Args:

        log_name(str): The name of the log to retrieve

    Yields:
        dict: A dictionary object for each event
    """

    # Get events from the local machine (None)
    handle = _get_handle(log_name)
    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ

    while True:
        # get list of some of the events
        events = win32evtlog.ReadEventLog(handle, flags, 0)
        if not events:
            # event log was updated and events are not ready to be given yet
            # rather than wait just return
            break
        for event in events:
            yield _make_event_dict(event)
    _close_handle(handle)


def _event_generator_with_time(log_name):
    """
    Sorts the results of the event generator

    Args:

        log_name (str): The name of the log to retrieve

    Yields:
        dict: A dictionary object for each event
    """
    # keys time
    time_parts = (
        "year",
        "month",
        "day",
        "hour",
        "minute",
        "second",
    )

    for event in _event_generator(log_name):
        event_info = {}
        for part in event:
            event_info[part] = event[part]

        for spot, key in enumerate(time_parts):
            event_info[key] = event["timeGenerated"][spot]

        yield event, event_info


def _event_generator_filter(log_name, all_requirements=True, **kwargs):
    """
    Will find events that meet the requirements in the filter. Can be any item
    in the return for the event.


    Args:

        log_name (str): The name of the log to retrieve

        all_requirements (bool): Should the results match all requirements.
            ``True`` matches all requirements. ``False`` matches any
            requirement.

    Kwargs:

        eventID (int): The event ID number

        eventType (int): The event type number. Valid options and their
            corresponding meaning are:

            - 0 : Success
            - 1 : Error
            - 2 : Warning
            - 4 : Information
            - 8 : Audit Success
            - 10 : Audit Failure

        year (int): The year

        month (int): The month

        day (int): The day of the month

        hour (int): The hour

        minute (int): The minute

        second (int): The second

        eventCategory (int): The event category number

        sid (sid): The SID of the user that created the event

        sourceName (str): The name of the event source

    Yields:
        dict: A dictionary object for each event

    CLI Example:

    .. code-block:: python

        # Return all events from the Security log with an ID of 1100
        _event_generator_filter("Security", eventID=1100)

        # Return all events from the System log with an Error (1) event type
        _event_generator_filter("System", eventType=1)

        # Return all events from System log with an Error (1) type, source is Service Control Manager, and data is netprofm
        _event_generator_filter("System", eventType=1, sourceName="Service Control Manager", data="netprofm")
    """

    for event, info in _event_generator_with_time(log_name):
        if all_requirements:
            # all keys need to match each other
            for key in kwargs:
                # ignore kwargs built-ins
                if key.startswith("__"):
                    continue
                # ignore function parameters
                if key in ["log_name", "all_arguments"]:
                    continue
                # Try to handle bytestrings
                if isinstance(info[key], bytes):
                    # try utf-8 first
                    try:
                        log.trace(
                            "utf-8: Does %s == %s",
                            repr(kwargs[key]),
                            repr(info[key].decode("utf-8")),
                        )
                        if kwargs[key] != info[key].decode("utf-8"):
                            # try utf-16 and strip null bytes
                            try:
                                log.trace(
                                    "utf-16: Does %s == %s",
                                    repr(kwargs[key]),
                                    repr(info[key].decode("utf-16").strip("\x00")),
                                )
                                if kwargs[key] != info[key].decode("utf-16").strip(
                                    "\x00"
                                ):
                                    break
                            except UnicodeDecodeError:
                                log.trace("Failed to decode (utf-16): %s", info[key])
                                break
                    except UnicodeDecodeError:
                        log.trace("Failed to decode (utf-8): %s", info[key])
                        break
                elif kwargs[key] != info[key]:
                    break
            else:
                yield info
        else:
            # just a single key pair needs to match
            for key in kwargs:
                # ignore kwargs built-ins
                if key.startswith("__"):
                    continue
                # ignore function parameters
                if key in ["log_name", "all_arguments"]:
                    continue
                # Try to handle bytestrings
                if isinstance(info[key], bytes):
                    # try utf-8 first
                    try:
                        log.trace(
                            "utf-8: Does %s == %s",
                            repr(kwargs[key]),
                            repr(info[key].decode("utf-8")),
                        )
                        if kwargs[key] == info[key].decode("utf-8"):
                            yield info
                    except UnicodeDecodeError:
                        log.trace("Failed to decode (utf-8): %s", info[key])
                    # try utf-16 and strip null bytes
                    try:
                        log.trace(
                            "utf-16: Does %s == %s",
                            repr(kwargs[key]),
                            repr(info[key].decode("utf-16").strip("\x00")),
                        )
                        if kwargs[key] == info[key].decode("utf-16").strip("\x00"):
                            yield info
                    except UnicodeDecodeError:
                        log.trace("Failed to decode (utf-16): %s", info[key])
                        break
                elif kwargs[key] == info[key]:
                    yield info


def get(log_name):
    """
    Get events from the specified log. Get a list of available logs using the
    :py:func:`win_event.get_log_names <salt.modules.win_event.get_log_names>`
    function.

    .. warning::
        Running this command on a log with thousands of events, such as the
        ``Applications`` log, can take a long time.

    Args:

        log_name(str): The name of the log to retrieve.

    Returns
        tuple: A tuple of events as dictionaries

    CLI Example:

    .. code-block:: bash

        salt '*' win_event.get Application
    """

    return tuple(_event_generator(log_name))


def query(log_name, query_text=None, records=20, latest=True, raw=False):
    """
    Query a log for a specific event_id. Return the top number of records
    specified. Use the
    :py:func:`win_event.get_log_names <salt.modules.win_event.get_log_names>`
    to see a list of available logs on the system.

    .. Note::
        You can use the Windows Event Viewer to create the XPath query for the
        ``query_text`` parameter. Click on ``Filter Current Log``, configure the
        filter, then click on the XML tab. Copy the text between the two
        ``<Select>`` tags. This will be the contents of the ``query_text``
        parameter. You will have to convert some codes. For example, ``&gt;``
        becomes ``>``, ``&lt;`` becomes ``<``. Additionally, you'll need to
        put spaces between comparison operators. For example: ``this >= that``.

    Args:

        log_name (str): The name of the log to query

        query_text (str): The filter to apply to the log

        records (int): The number of records to return

        latest (bool): ``True`` will return the newest events. ``False`` will
            return the oldest events. Default is ``True``

        raw (bool): ``True`` will return the raw xml results. ``False`` will
            return the xml converted to a dictionary. Default is ``False``

    Returns:
        list: A list of dict objects that contain information about the event

    CLI Example:

    .. code-block:: bash

        # Return the 20 most recent events from the Application log with an event ID of 22
        salt '*' win_event.query Application "*[System[(EventID=22)]]"

        # Return the 20 most recent events from the Application log with an event ID of 22
        # Return raw xml
        salt '*' win_event.query Application "*[System[(EventID=22)]]" raw=True

        # Return the 20 oldest events from the Application log with an event ID of 22
        salt '*' win_event.query Application "*[System[(EventID=22)]]" latest=False

        # Return the 20 most recent Critical (1) events from the Application log in the last 12 hours
        salt '*" win_event.query Application "*[System[(Level=1) and TimeCreated[timediff(@SystemTime) <= 43200000]]]"

        # Return the 5 most recent Error (2) events from the application log
        salt '*" win_event.query Application "*[System[(Level=2)]]" records=5

        # Return the 20 most recent Warning (3) events from the Windows PowerShell log where the Event Source is PowerShell
        salt '*" win_event.query "Windows PowerShell" "*[System[Provider[@Name='PowerShell'] and (Level=3)]]"

        # Return the 20 most recent Information (0 or 4) events from the Microsoft-Windows-PowerShell/Operational on 2022-08-24 with an Event ID of 4103
        salt '*" win_event.query "Microsoft-Windows-PowerShell/Operational" "*[System[(Level=4 or Level=0) and (EventID=4103) and TimeCreated[@SystemTime >= '2022-08-24T06:00:00.000Z']]]"

        # Return the 20 most recent Information (0 or 4) events from the Microsoft-Windows-PowerShell/Operational within the last hour
        salt '*" win_event.query "Microsoft-Windows-PowerShell/Operational" "*[System[(Level=4 or Level=0) and TimeCreated[timediff(@SystemTime) <= 3600000]]]"
    """
    if not isinstance(latest, bool):
        raise CommandExecutionError("latest must be a boolean")

    direction = win32evtlog.EvtQueryReverseDirection
    if not latest:
        direction = win32evtlog.EvtQueryForwardDirection

    results = win32evtlog.EvtQuery(log_name, direction, query_text, None)

    event_list = []
    for evt in win32evtlog.EvtNext(results, records):
        if raw:
            res = win32evtlog.EvtRender(evt, 1)
        else:
            res = xmltodict.parse(win32evtlog.EvtRender(evt, 1))
        event_list.append(res)

    return event_list


def get_filtered(log_name, all_requirements=True, **kwargs):
    """
    Will find events that match the fields and values specified in the kwargs.
    Kwargs can be any item in the return for the event.

    .. warning::
        Running this command on a log with thousands of events, such as the
        ``Applications`` log, can take a long time.

    Args:

        log_name (str): The name of the log to retrieve

        all_requirements (bool): ``True`` matches all requirements. ``False``
            matches any requirement. Default is ``True``

    Kwargs:

        eventID (int): The event ID number

        eventType (int): The event type number. Valid options and their
            corresponding meaning are:

            - 0 : Success
            - 1 : Error
            - 2 : Warning
            - 4 : Information
            - 8 : Audit Success
            - 10 : Audit Failure

        year (int): The year

        month (int): The month

        day (int): The day of the month

        hour (int): The hour

        minute (int): The minute

        second (int): The second

        eventCategory (int): The event category number

        sid (sid): The SID of the user that created the event

        sourceName (str): The name of the event source

    Returns:
        tuple: A tuple of dicts of each filtered event

    CLI Example:

    .. code-block:: bash

        # Return all events from the Security log with an ID of 1100
        salt "*" win_event.get_filtered Security eventID=1100

        # Return all events from the System log with an Error (1) event type
        salt "*" win_event.get_filtered System eventType=1

        # Return all events from System log with an Error (1) type, source is Service Control Manager, and data is netprofm
        salt "*" win_event.get_filtered System eventType=1 sourceName="Service Control Manager" data="netprofm"

        # Return events from the System log that match any of the kwargs below
        salt "*" win_event.get_filtered System eventType=1 sourceName="Service Control Manager" data="netprofm" all_requirements=False
    """

    return tuple(_event_generator_filter(log_name, all_requirements, **kwargs))


def get_log_names():
    """
    Get a list of event logs available on the system

    Returns:
        list: A list of event logs available on the system

    CLI Example:

    .. code-block:: bash

        salt "*" win_event.get_log_names
    """
    h = win32evtlog.EvtOpenChannelEnum(None)
    log_names = []
    while win32evtlog.EvtNextChannelPath(h) is not None:
        log_names.append(win32evtlog.EvtNextChannelPath(h))
    return log_names


def add(
    log_name,
    event_id,
    event_category=0,
    event_type=None,
    event_strings=None,
    event_data=None,
    event_sid=None,
):
    """
    Adds an event to the application event log.

    Args:

        log_name (str): The name of the application or source

        event_id (int): The event ID

        event_category (int): The event category

        event_type (str): The event category. Must be one of:

            - Success
            - Error
            - Warning
            - Information
            - AuditSuccess
            - AuditFailure

        event_strings (list): A list of strings

        event_data (bytes): Event data. Strings will be converted to bytes

        event_sid (sid): The SID for the event

    Raises:
        CommandExecutionError: event_id is not an integer
        CommandExecutionError: event_category is not an integer
        CommandExecutionError: event_type is not one of the valid event types
        CommandExecutionError: event_strings is not a list or string

    CLI Example:

    .. code-block:: bash

        # A simple Application event log warning entry
        salt '*' win_event.add Application 1234 12 Warning

        # A more complex System event log information entry
        salt '*' win_event.add System 1234 12 Information "['Event string data 1', 'Event string data 2']" "Some event data"

        # Log to the System Event log with the source "Service Control Manager"
        salt '*' win_event.add "Service Control Manager" 1234 12 Warning "['Event string data 1', 'Event string data 2']" "Some event data"

        # Log to the PowerShell event log with the source "PowerShell (PowerShell)"
        salt-call --local win_event.add "PowerShell" 6969 12 Warning
    """

    try:
        event_id = int(event_id)
    except TypeError:
        raise CommandExecutionError("event_id must be an integer")

    try:
        event_category = int(event_category)
    except TypeError:
        raise CommandExecutionError("event_category must be an integer")

    event_types = {
        "Success": 0x0000,
        "Error": 0x0001,
        "Warning": 0x0002,
        "Information": 0x0004,
        "AuditSuccess": 0x0008,
        "AuditFailure": 0x0010,
        0x0000: "Success",
        0x0001: "Error",
        0x0002: "Warning",
        0x0004: "Information",
        0x0008: "AuditSuccess",
        0x0010: "AuditFailure",
    }

    if event_type is None:
        event_type = event_types["Error"]
    elif event_type not in event_types:
        msg = "Incorrect event type: {}".format(event_type)
        raise CommandExecutionError(msg)
    else:
        event_type = event_types[event_type]

    if event_strings is not None:
        if isinstance(event_strings, str):
            event_strings = [event_strings]
        elif not isinstance(event_strings, list):
            raise CommandExecutionError("event_strings must be a list")

    if event_data is not None:
        event_data = salt.utils.stringutils.to_bytes(event_data)

    # https://docs.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-reporteventw
    win32evtlogutil.ReportEvent(
        appName=log_name,
        eventID=int(event_id),
        eventCategory=int(event_category),
        eventType=event_type,
        strings=event_strings,
        data=event_data,
        sid=event_sid,
    )


def clear(log_name, backup=None):
    """
    Clears the specified event log.

    .. note::
        A clear log event will be added to the log after it is cleared.

    Args:

        log_name (str): The name of the log to clear

        backup (str): Path to backup file

    CLI Example:

    .. code-block:: bash

        salt "*" win_event.clear Application
    """

    handle = _get_handle(log_name)
    win32evtlog.ClearEventLog(handle, backup)
    _close_handle(handle)


def count(log_name):
    """
    Gets the number of events in the specified.

    Args:

        log_name (str): The name of the log

    Returns:
        int: The number of events the log contains

    CLI Example:

    .. code-block:: bash

        salt "*" win_event.count Application
    """

    handle = _get_handle(log_name)
    number_of_events = win32evtlog.GetNumberOfEventLogRecords(handle)
    _close_handle(handle)
    return number_of_events
