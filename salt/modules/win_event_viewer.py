# -*- coding: utf-8 -*-
'''
:codeauthor: Charles McMarrow <cmcmarrow@saltstack.com>
gives access to Windows event log
'''

from __future__ import absolute_import

# Import Python libs
import logging
import collections

# Import Salt Libs
import salt.utils.platform

# Import Third Party Libs
try:
    import win32evtlog
    import win32evtlogutil
    import winerror
    import pywintypes
    IMPORT_STATUS = True
except ImportError:
    IMPORT_STATUS = False

# keys of all the parts of a Event supported by the API
EVENT_PARTS = ('closingRecordNumber',
               'computerName',
               'data',
               'eventCategory',
               'eventID',
               'eventType',
               'recordNumber',
               'reserved',
               'reservedFlags',
               'sid',
               'sourceName',
               'stringInserts',
               'timeGenerated',
               'timeWritten'
)

# keys time
TIME_PARTS = ('year',
              'month',
              'day',
              'hour',
              'minute',
              'second'
)
TimeTuple = collections.namedtuple('TimeTuple', 'year, month, day, hour, minute, second')


log = logging.getLogger(__name__)
__virtualname__ = 'win_event_viewer'


def __virtual__():
    '''
    Load only on minions running on Windows.
    '''

    if not salt.utils.platform.is_windows() or not IMPORT_STATUS:
        return False, 'win_event_viewer: most be on windows'
    return __virtualname__


def _change_str_to_bytes(data, encoding='utf-8', encode_keys=False):
    '''
    Will make string objects into byte objects.
    Warning this function will destroy the data object and objects that data links to.

    data
        object

    encoding
        str
    encode_keys
        bool
        if false key strings will not be turned into bytes

    return
        new object
    '''

    if isinstance(data, dict):
        new_dict = {}
        # recursively check every item in dict
        for key in data:
            item = _change_str_to_bytes(data[key], encoding)
            if encode_keys:
                # keys that are strings most be made into bytes
                key = _change_str_to_bytes(key, encoding)
            new_dict[key] = item
        data = new_dict
    elif isinstance(data, list):
        new_list = []
        # recursively check every item in list
        for item in data:
            new_list.append(_change_str_to_bytes(item, encoding))
        data = new_list
    elif isinstance(data, tuple):
        new_list = []
        # recursively check every item in list
        for item in data:
            new_list.append(_change_str_to_bytes(item, encoding))
        data = tuple(new_list)
    elif isinstance(data, str):
        # data is turning into bytes because if was a string
        data = data.encode(encoding)

    return data


def _get_raw_time(time):
    '''
    Will make a pywintypes.datetime into a TimeTuple.

    time
        pywintypes.datetime

    return
        TimeTuple
    '''

    return TimeTuple._make((time.year, time.month, time.day, time.hour, time.minute, time.second))


def make_event_dict(event):
    '''
    Will make a PyEventLogRecord into a dict.

    event
        PyEventLogRecord

    return
        dict
    '''

    event_dict = {}
    for event_part in EVENT_PARTS:
        # get object value and add it to the event dict
        event_dict[event_part] = getattr(event, event_part[0].upper() + event_part[1:], None)

    # format items
    event_dict['eventID'] = winerror.HRESULT_CODE(event_dict['eventID'])
    if event_dict['sid'] is not None:
        event_dict['sid'] = event_dict['sid'].GetSidIdentifierAuthority()
    event_dict['timeGenerated'] = _get_raw_time(event_dict['timeGenerated'])
    event_dict['timeWritten'] = _get_raw_time(event_dict['timeWritten'])

    return _change_str_to_bytes(event_dict)


def _get_event_handler(log_name, target_computer=None):
    '''
    Will try to open a PyHANDLE.

    log_name
        str

    target_computer
        None or str

    return
        PyHANDLE
    '''

    # TODO: upgrade windows token
    # 'log close' can fail if this is not done
    try:
        return win32evtlog.OpenEventLog(target_computer, log_name)
    except pywintypes.error:
        raise FileNotFoundError('Log "{0}" of "{1}" can not be found or access was denied!'.format(log_name,
                                                                                                   target_computer))


def _close_event_handler(handler):
    '''
    Will close the event handler.

    handler:
        PyHANDLE
    '''

    # TODO: downgrade windows token
    win32evtlog.CloseEventLog(handler)


def get_event_generator(log_name, target_computer=None, raw=False):
    '''
    Will get all log events one by one.
    Warning events are not in exact order.

    log_name
        str

    target_computer
        None or str
    raw
        bool
        True: PyEventLogRecord
        False: dict

    return
        PyEventLogRecord or dict
    '''

    handler = _get_event_handler(log_name, target_computer)
    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
    event_count = 0

    while win32evtlog.GetNumberOfEventLogRecords(handler) > event_count:
        # get list of some of the events
        events = win32evtlog.ReadEventLog(handler, flags, 0)
        if not events:
            # event log was updated and events are not ready to be given yet
            # rather than wait just return
            break
        for event in events:
            event_count += 1
            if raw:
                yield event
            else:
                yield make_event_dict(event)
    _close_event_handler(handler)


def get_events(log_name, target_computer=None, raw=False):
    '''
    Will make a tuple of log events.

    log_name:
        str

    target_computer:
        None or str

    raw:
        bool
        True: PyEventLogRecord
        False: dict

    return
        tuple
    '''

    return tuple(get_event_generator(log_name, target_computer, raw))


def get_event_sorted_by_info_generator(log_name, target_computer=None):
    '''
    Makes keys to event

    log_name
        str

    target_computer
        None or str

    return
        dict
    '''

    for event in get_event_generator(log_name, target_computer):
        event_info = {}
        for part in event:
            event_info[part] = event[part]

        for spot, key in enumerate(TIME_PARTS):
            event_info[key] = event['timeGenerated'][spot]

        yield event, event_info


def get_events_sorted_by_info(log_name, target_computer=None):
    '''
    Make dict of sorted events

    log_name:
        str

    target_computer
        None or str

    return
        dict
    '''

    event_info = {event_part: collections.defaultdict(list) for event_part in EVENT_PARTS + TIME_PARTS}
    for event, info in get_event_sorted_by_info_generator(log_name, target_computer):
        for part in info:
            event_info[part][info.get(part)].append(event)

    return event_info


def get_event_filter_generator(log_name, target_computer=None, all_requirements=True, **kwargs):
    '''
    Will find events that meet the requirements

    log_name
        str

    target_computer
        None or str

    all_requirements
        bool
        True: all requirements most be meet
        False: only a single requirement most be meet

    kwargs:
        requirements for the events

    return
        dict
    '''

    for event, info in get_event_sorted_by_info_generator(log_name, target_computer):
        if all_requirements:
            # all keys need to match each other
            for key in kwargs:
                if kwargs[key] != info[key]:
                    break
            else:
                yield event
        else:
            # just a single key par needs to match
            if any([kwargs[key] == info[key] for key in kwargs]):
                yield event


def get_events_filter(log_name, target_computer=None, all_requirements=True, **kwargs):
    '''
    Will find events that meet the requirements.

    log_name:
        str

    target_computer
        None or str

    all_requirements
        bool
        True: all requirements most be meet
        False: only a single requirement most be meet

    kwargs
        requirements for the events

    return
        list
    '''

    return tuple(get_event_filter_generator(log_name, target_computer, all_requirements, **kwargs))


def log_event(application_name, event_id, **kwargs):
    '''
    Adds event to application log.

    application_name
        str

    event_id
        int

    kwargs
        parts of event
    '''

    win32evtlogutil.ReportEvent(application_name, event_id, **kwargs)


def clear_log(log_name, target_computer=None):
    '''
    Clears event log.
    Note that a clear log event will be add it after the log was clear

    log_name
        str

    target_computer
        None or str
    '''

    handler = _get_event_handler(log_name, target_computer)
    win32evtlog.ClearEventLog(handler, log_name)
    _close_event_handler(handler)


def get_number_of_events(log_name, target_computer=None):
    '''
    Gets the number of events in a log.

    log_name:
        str

    target_computer
        None or str

    return
        int
    '''

    handler = _get_event_handler(log_name, target_computer)
    number_of_events = win32evtlog.GetNumberOfEventLogRecords(handler)
    _close_event_handler(handler)
    return number_of_events
