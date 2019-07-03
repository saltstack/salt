# -*- coding: utf-8 -*-
'''
test of win_event_viewer
'''


# Import Salt Libs
import salt.utils.platform
import salt.modules.win_event_viewer as win_event_viewer

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.helpers import destructiveTest
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Third Party Libs
try:
    import win32evtlog
    import win32evtlogutil
    import pywintypes
except ImportError:
    pass


MAX_EVENT_LOOK_UP = 2000


class MockTime(object):
    def __init__(self, year=2000, month=1, day=1, hour=1, minute=1, second=1):
        self.year = year
        self.month = month
        self.day = day
        self.hour = hour
        self.minute = minute
        self.second = second


class MockEvent(object):
    def __init__(self,
                 closing_record_number=0,
                 computer_name='PC',
                 data=bytes(),
                 event_category=117,
                 event_id=101,
                 event_type=4,
                 record_number=0,
                 reserved_data=4,
                 reserved_flags=0,
                 sid=None,
                 source_name=0,
                 string_inserts=("cat", "m"),
                 time_generated=None,
                 time_written=None):

        self.ClosingRecordNumber = closing_record_number
        self.ComputerName = computer_name
        self.Data = data
        self.EventCategory = event_category
        self.EventID = event_id
        self.EventType = event_type
        self.RecordNumber = record_number
        # 'reserved' is a build in function
        self.Reserved = reserved_data
        self.ReservedFlags = reserved_flags
        self.Sid = sid
        self.SourceName = source_name
        self.StringInserts = string_inserts

        if time_generated is None:
            time_generated = MockTime()
        self.TimeGenerated = time_generated

        if time_written is None:
            time_written = MockTime()
        self.TimeWritten = time_written


MOCK_EVENT_1 = MockEvent()
MOCK_EVENT_2 = MockEvent(event_category=404, time_generated=MockTime(2019, 4, 6, 2, 3, 12))
MOCK_EVENT_3 = MockEvent(reserved_data=2, string_inserts=("fail...", "error..."))
MOCK_EVENT_4 = MockEvent(event_category=301, event_id=9)
MOCK_EVENT_5 = MockEvent(event_category=300, event_id=5)
MOCK_EVENT_6 = MockEvent(computer_name='sky',
                         time_generated=MockTime(1997, 8, 29, 2, 14, 0),
                         string_inserts=("'I am a live!'", "launching..."))

EVENTS = (
    MOCK_EVENT_1,
    MOCK_EVENT_2,
    MOCK_EVENT_3,
    MOCK_EVENT_4,
    MOCK_EVENT_5,
    MOCK_EVENT_6
)


class MockHandler(object):
    def __init__(self, events=None):
        if events is None:
            events = []
        self.events = events
        self.generator = self.get_generator()

    def __len__(self):
        return len(self.events)

    def get_generator(self):
        for event in self.events:
            yield [event]

    def read(self):
        try:
            return next(self.generator)
        except StopIteration:
            return []


def mock_read_event_log(handler, flag, start):
    assert isinstance(flag, int) and flag == abs(flag)
    assert isinstance(start, int) and start == abs(start)
    return handler.read()


def mock_get_number_of_event_log_records(handler):
    return len(handler)


@skipIf(not salt.utils.platform.is_windows(), "Windows is required")
class WinEventViewerSimpleTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.win_iis
    '''

    def setup_loader_modules(self):
        return {win_event_viewer: {}}

    def test__str_to_bytes(self):
        data = {'key1': 'item1',
                'key2': [1, 2, 'item2'],
                'key3': 45,
                45: str}

        new_data = win_event_viewer._change_str_to_bytes(data, 'utf-8', False)

        self.assertTrue('key1' in new_data)

        self.assertEqual(new_data.get('key1'), 'item1'.encode('utf-8'))
        self.assertEqual(new_data.get('key2')[2], 'item2'.encode('utf-8'))

    def test_2__str_to_bytes(self):
        data = {'key1': 'item1',
                'key2': [1, 2, 'item2'],
                'key3': 45,
                45: str}

        new_data = win_event_viewer._change_str_to_bytes(data, 'CP1252', True)

        self.assertTrue('key1'.encode('CP1252') in new_data)
        self.assertTrue('key2'.encode('CP1252') in new_data)
        self.assertTrue('key3'.encode('CP1252') in new_data)

        self.assertEqual(new_data.get('key1'.encode('CP1252')), 'item1'.encode('CP1252'))
        self.assertEqual(new_data.get('key2'.encode('CP1252'))[2], 'item2'.encode('CP1252'))

    def test__get_raw_time(self):
        mock_time = MockTime(2019, 7, 2, 10, 8, 19)
        raw_time = win_event_viewer._get_raw_time(mock_time)
        self.assertEqual(raw_time, (2019, 7, 2, 10, 8, 19))


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(not salt.utils.platform.is_windows(), "Windows is required")
class WinEventViewerMockTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.win_iis
    '''

    def setup_loader_modules(self):
        return {win_event_viewer: {}}

    def test__get_event_handler(self):
        with patch.object(win32evtlog, 'OpenEventLog', return_value=MockHandler()) as open_event_log:
            ret = win_event_viewer._get_event_handler("System", None)
            open_event_log.called_once_with("System", None)
            self.assertIsInstance(ret, MockHandler)

    def test_fail__get_event_handler(self):
        with patch.object(win32evtlog, 'OpenEventLog', side_effect=pywintypes.error()) as open_event_log:
            open_event_log.called_once_with("System", None)
            self.assertRaises(FileNotFoundError, win_event_viewer._get_event_handler, "System")

    @staticmethod
    def test__close_event_handler():
        with patch.object(win32evtlog, 'CloseEventLog', return_value=None) as close_event_log:
            handler = MockHandler()
            win_event_viewer._close_event_handler(MockHandler())
            close_event_log.called_once_with(handler)

    def test_get_event_generator(self):
        handler = MockHandler(EVENTS)

        with patch.object(win_event_viewer, "_get_event_handler", return_value=handler) as _get_event_handler:
            with patch.object(win_event_viewer, "_close_event_handler", return_value=None) as _close_event_handler:
                with patch.object(win32evtlog, 'ReadEventLog', wraps=mock_read_event_log) as ReadEventLog:
                    with patch.object(win32evtlog,
                                      'GetNumberOfEventLogRecords',
                                      wraps=mock_get_number_of_event_log_records) as GetNumberOfEventLogRecords:
                        ret = tuple(win_event_viewer.get_event_generator("System", target_computer=None, raw=False))

                        self.assertIsInstance(ret, tuple)
                        self.assertTrue(all([isinstance(event, dict)for event in ret]))

                        _get_event_handler.assert_called_once_with('System', None)
                        _close_event_handler.assert_called_once_with(handler)

                        self.assertEqual(ReadEventLog.call_count, len(handler))
                        self.assertEqual(GetNumberOfEventLogRecords.call_count, len(handler) + 1)

    def test_raw_get_event_generator(self):
        handler = MockHandler(EVENTS)

        with patch.object(win_event_viewer, "_get_event_handler", return_value=handler) as _get_event_handler:
            with patch.object(win_event_viewer, "_close_event_handler", return_value=None) as _close_event_handler:
                with patch.object(win32evtlog, 'ReadEventLog', wraps=mock_read_event_log) as ReadEventLog:
                    with patch.object(win32evtlog,
                                      'GetNumberOfEventLogRecords',
                                      wraps=mock_get_number_of_event_log_records) as GetNumberOfEventLogRecords:
                        ret = tuple(win_event_viewer.get_event_generator("System", target_computer=None, raw=True))

                        self.assertIsInstance(ret, tuple)
                        self.assertTrue(all([isinstance(event, MockEvent) for event in ret]))

                        _get_event_handler.assert_called_once_with('System', None)
                        _close_event_handler.assert_called_once_with(handler)

                        self.assertEqual(ReadEventLog.call_count, len(handler))
                        self.assertEqual(GetNumberOfEventLogRecords.call_count, len(handler) + 1)

    def test_get_events(self):
        handler = MockHandler(EVENTS)

        with patch.object(win_event_viewer, "_get_event_handler", return_value=handler) as _get_event_handler:
            with patch.object(win_event_viewer, "_close_event_handler", return_value=None) as _close_event_handler:
                with patch.object(win32evtlog, 'ReadEventLog', wraps=mock_read_event_log) as ReadEventLog:
                    with patch.object(win32evtlog,
                                      'GetNumberOfEventLogRecords',
                                      wraps=mock_get_number_of_event_log_records) as GetNumberOfEventLogRecords:
                        ret = win_event_viewer.get_events("System", target_computer=None, raw=False)

                        self.assertIsInstance(ret, tuple)
                        self.assertTrue(all([isinstance(event, dict)for event in ret]))

                        _get_event_handler.assert_called_once_with('System', None)
                        _close_event_handler.assert_called_once_with(handler)

                        self.assertEqual(ReadEventLog.call_count, len(handler))
                        self.assertEqual(GetNumberOfEventLogRecords.call_count, len(handler) + 1)

    def test_raw_get_events(self):
        handler = MockHandler(EVENTS)

        with patch.object(win_event_viewer, "_get_event_handler", return_value=handler) as _get_event_handler:
            with patch.object(win_event_viewer, "_close_event_handler", return_value=None) as _close_event_handler:
                with patch.object(win32evtlog, 'ReadEventLog', wraps=mock_read_event_log) as ReadEventLog:
                    with patch.object(win32evtlog,
                                      'GetNumberOfEventLogRecords',
                                      wraps=mock_get_number_of_event_log_records) as GetNumberOfEventLogRecords:
                        ret = win_event_viewer.get_events("System", target_computer=None, raw=True)

                        self.assertIsInstance(ret, tuple)
                        self.assertTrue(all([isinstance(event, MockEvent) for event in ret]))

                        _get_event_handler.assert_called_once_with('System', None)
                        _close_event_handler.assert_called_once_with(handler)

                        self.assertEqual(ReadEventLog.call_count, len(handler))
                        self.assertEqual(GetNumberOfEventLogRecords.call_count, len(handler) + 1)

    def test_get_event_sorted_by_info_generator(self):
        handler = MockHandler(EVENTS)

        with patch.object(win_event_viewer, "_get_event_handler", return_value=handler) as _get_event_handler:
            with patch.object(win_event_viewer, "_close_event_handler", return_value=None) as _close_event_handler:
                with patch.object(win32evtlog, 'ReadEventLog', wraps=mock_read_event_log) as ReadEventLog:
                    with patch.object(win32evtlog,
                                      'GetNumberOfEventLogRecords',
                                      wraps=mock_get_number_of_event_log_records) as GetNumberOfEventLogRecords:
                        ret = tuple(win_event_viewer.get_event_sorted_by_info_generator("System", target_computer=None))

                        self.assertIsInstance(ret, tuple)
                        self.assertTrue(all([isinstance(event_info, tuple) for event_info in ret]))

                        _get_event_handler.assert_called_once_with('System', None)
                        _close_event_handler.assert_called_once_with(handler)

                        self.assertEqual(ReadEventLog.call_count, len(handler))
                        self.assertEqual(GetNumberOfEventLogRecords.call_count, len(handler) + 1)

                        self.assertEqual(ret[1][1].get('eventCategory'), 404)
                        self.assertEqual(ret[2][1].get('stringInserts'), (b'fail...', b'error...'))
                        self.assertEqual(ret[4][1].get('eventID'), 5)
                        self.assertEqual(ret[5][1].get('computerName'), b'sky')
                        self.assertEqual(ret[5][1].get('timeGenerated'), (1997, 8, 29, 2, 14, 0))

    def test_get_events_sorted_by_info(self):
        handler = MockHandler(EVENTS)

        with patch.object(win_event_viewer, "_get_event_handler", return_value=handler) as _get_event_handler:
            with patch.object(win_event_viewer, "_close_event_handler", return_value=None) as _close_event_handler:
                with patch.object(win32evtlog, 'ReadEventLog', wraps=mock_read_event_log) as ReadEventLog:
                    with patch.object(win32evtlog,
                                      'GetNumberOfEventLogRecords',
                                      wraps=mock_get_number_of_event_log_records) as GetNumberOfEventLogRecords:
                        ret = win_event_viewer.get_events_sorted_by_info("System", target_computer=None)

                        self.assertIsInstance(ret, dict)

                        _get_event_handler.assert_called_once_with('System', None)
                        _close_event_handler.assert_called_once_with(handler)

                        self.assertEqual(ReadEventLog.call_count, len(handler))
                        self.assertEqual(GetNumberOfEventLogRecords.call_count, len(handler) + 1)

                        self.assertEqual(ret.get('eventID').get(5), [{'closingRecordNumber': 0,
                                                                      'computerName': b'PC',
                                                                      'data': b'',
                                                                      'eventCategory': 300,
                                                                      'eventID': 5,
                                                                      'eventType': 4,
                                                                      'recordNumber': 0,
                                                                      'reserved': 4,
                                                                      'reservedFlags': 0,
                                                                      'sid': None,
                                                                      'sourceName': 0,
                                                                      'stringInserts': (b'cat', b'm'),
                                                                      'timeGenerated': (2000, 1, 1, 1, 1, 1),
                                                                      'timeWritten': (2000, 1, 1, 1, 1, 1)}])

                        self.assertEqual(ret.get('computerName').get(b'sky'),
                                         [{'closingRecordNumber': 0,
                                           'computerName': b'sky',
                                           'data': b'',
                                           'eventCategory': 117,
                                           'eventID': 101,
                                           'eventType': 4,
                                           'recordNumber': 0,
                                           'reserved': 4,
                                           'reservedFlags': 0,
                                           'sid': None,
                                           'sourceName': 0,
                                           'stringInserts': (b"'I am a live!'", b'launching...'),
                                           'timeGenerated': (1997, 8, 29, 2, 14, 0),
                                           'timeWritten': (2000, 1, 1, 1, 1, 1)}])

    def test_get_event_filter_generator(self):
        handler = MockHandler(EVENTS)

        with patch.object(win_event_viewer, "_get_event_handler", return_value=handler) as _get_event_handler:
            with patch.object(win_event_viewer, "_close_event_handler", return_value=None) as _close_event_handler:
                with patch.object(win32evtlog, 'ReadEventLog', wraps=mock_read_event_log) as ReadEventLog:
                    with patch.object(win32evtlog,
                                      'GetNumberOfEventLogRecords',
                                      wraps=mock_get_number_of_event_log_records) as GetNumberOfEventLogRecords:
                        ret = tuple(win_event_viewer.get_event_filter_generator("System",
                                                                                target_computer=None,
                                                                                all_requirements=True,
                                                                                eventID=101,
                                                                                sid=None))
                        self.assertIsInstance(ret, tuple)

                        _get_event_handler.assert_called_once_with('System', None)
                        _close_event_handler.assert_called_once_with(handler)

                        self.assertEqual(ReadEventLog.call_count, len(handler))
                        self.assertEqual(GetNumberOfEventLogRecords.call_count, len(handler) + 1)

                        self.assertEqual(len(ret), 4)

    def test_all_get_event_filter_generator(self):
        handler = MockHandler(EVENTS)

        with patch.object(win_event_viewer, "_get_event_handler", return_value=handler) as _get_event_handler:
            with patch.object(win_event_viewer, "_close_event_handler", return_value=None) as _close_event_handler:
                with patch.object(win32evtlog, 'ReadEventLog', wraps=mock_read_event_log) as ReadEventLog:
                    with patch.object(win32evtlog,
                                      'GetNumberOfEventLogRecords',
                                      wraps=mock_get_number_of_event_log_records) as GetNumberOfEventLogRecords:
                        ret = tuple(win_event_viewer.get_event_filter_generator("System",
                                                                                target_computer=None,
                                                                                all_requirements=False,
                                                                                eventID=101,
                                                                                sid=None))
                        self.assertIsInstance(ret, tuple)

                        _get_event_handler.assert_called_once_with('System', None)
                        _close_event_handler.assert_called_once_with(handler)

                        self.assertEqual(ReadEventLog.call_count, len(handler))
                        self.assertEqual(GetNumberOfEventLogRecords.call_count, len(handler) + 1)

                        self.assertEqual(len(ret), 6)

    def test_get_events_filter(self):
        handler = MockHandler(EVENTS)

        with patch.object(win_event_viewer, "_get_event_handler", return_value=handler) as _get_event_handler:
            with patch.object(win_event_viewer, "_close_event_handler", return_value=None) as _close_event_handler:
                with patch.object(win32evtlog, 'ReadEventLog', wraps=mock_read_event_log) as ReadEventLog:
                    with patch.object(win32evtlog,
                                      'GetNumberOfEventLogRecords',
                                      wraps=mock_get_number_of_event_log_records) as GetNumberOfEventLogRecords:
                        ret = tuple(win_event_viewer.get_events_filter("System",
                                                                       target_computer=None,
                                                                       all_requirements=True,
                                                                       eventID=101,
                                                                       sid=None))
                        self.assertIsInstance(ret, tuple)

                        _get_event_handler.assert_called_once_with('System', None)
                        _close_event_handler.assert_called_once_with(handler)

                        self.assertEqual(ReadEventLog.call_count, len(handler))
                        self.assertEqual(GetNumberOfEventLogRecords.call_count, len(handler) + 1)

                        self.assertEqual(len(ret), 4)

    def test_all_get_events_filter(self):
        handler = MockHandler(EVENTS)

        with patch.object(win_event_viewer, "_get_event_handler", return_value=handler) as _get_event_handler:
            with patch.object(win_event_viewer, "_close_event_handler", return_value=None) as _close_event_handler:
                with patch.object(win32evtlog, 'ReadEventLog', wraps=mock_read_event_log) as ReadEventLog:
                    with patch.object(win32evtlog,
                                      'GetNumberOfEventLogRecords',
                                      wraps=mock_get_number_of_event_log_records) as GetNumberOfEventLogRecords:
                        ret = tuple(win_event_viewer.get_events_filter("System",
                                                                       target_computer=None,
                                                                       all_requirements=False,
                                                                       eventID=101,
                                                                       sid=None))
                        self.assertIsInstance(ret, tuple)

                        _get_event_handler.assert_called_once_with('System', None)
                        _close_event_handler.assert_called_once_with(handler)

                        self.assertEqual(ReadEventLog.call_count, len(handler))
                        self.assertEqual(GetNumberOfEventLogRecords.call_count, len(handler) + 1)

                        self.assertEqual(len(ret), 6)

    @staticmethod
    def test_clear_log():
        with patch.object(win32evtlogutil, 'ReportEvent', return_value=None) as ReportEvent:
            win_event_viewer.log_event('salt', 117, eventType=1)
            ReportEvent.assert_called_once_with('salt', 117, eventType=1)

    @staticmethod
    def test_log_event():
        handler = MockHandler(EVENTS)

        with patch.object(win_event_viewer, "_get_event_handler", return_value=handler) as _get_event_handler:
            with patch.object(win_event_viewer, "_close_event_handler", return_value=None) as _close_event_handler:
                with patch.object(win32evtlog, 'ClearEventLog', return_value=None) as ClearEventLog:
                    win_event_viewer.clear_log('System', target_computer=None)

                    _get_event_handler.assert_called_once_with('System', None)
                    _close_event_handler.assert_called_once_with(handler)

                    ClearEventLog.assert_called_once_with(handler, 'System')

    @staticmethod
    def test_get_number_of_events():
        handler = MockHandler(EVENTS)

        with patch.object(win_event_viewer, "_get_event_handler", return_value=handler) as _get_event_handler:
            with patch.object(win_event_viewer, "_close_event_handler", return_value=None) as _close_event_handler:
                with patch.object(win32evtlog, 'GetNumberOfEventLogRecords',
                                  return_value=None) as GetNumberOfEventLogRecords:
                    win_event_viewer.get_number_of_events('System', target_computer=None)

                    _get_event_handler.assert_called_once_with('System', None)
                    _close_event_handler.assert_called_once_with(handler)

                    GetNumberOfEventLogRecords.assert_called_once_with(handler)


@destructiveTest
@skipIf(not salt.utils.platform.is_windows(), "Windows is required")
class WinEventViewerDestructiveTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.win_iis
    All test are destructive because their actions will add events to the security log.
    Even if the method is only reading a log or getting the size of a log.
    DONT!!!!! add a "clear log" test for security reasons!!!!!
    '''

    def setup_loader_modules(self):
        return {win_event_viewer: {}}

    def test_get_event_generator(self):
        for number, event in enumerate(win_event_viewer.get_event_generator("System",
                                                                            target_computer=None,
                                                                            raw=False)):

            self.assertIsInstance(event, dict)
            for event_part in win_event_viewer.EVENT_PARTS:
                self.assertTrue(event_part in event)

            if number == MAX_EVENT_LOOK_UP:
                break

    def test_raw_get_event_generator(self):
        # TODO: type(event) does not work as of 7/3/2019.
        # its a upstream problem and python will crash if you call it
        # when this upstream problem is no more add a self.assertIsInstance pls

        for number, event in enumerate(win_event_viewer.get_event_generator("System",
                                                                            target_computer=None,
                                                                            raw=True)):

            for event_part in win_event_viewer.EVENT_PARTS:
                self.assertTrue(hasattr(event, event_part[0].upper() + event_part[1:]))

            if number == MAX_EVENT_LOOK_UP:
                break

    def test_get_event_sorted_by_info_generator(self):
        for number, ret in enumerate(win_event_viewer.get_event_sorted_by_info_generator("Application",
                                                                                         target_computer=None)):
            event, event_info = ret[0], ret[1]
            for event_part in win_event_viewer.EVENT_PARTS:
                self.assertEqual(event.get(event_part), event_info.get(event_part))

            for event_part in win_event_viewer.TIME_PARTS:
                self.assertTrue(event_part in event_info)

            if number == MAX_EVENT_LOOK_UP:
                break

    def test_get_event_filter_generator(self):
        for number, event in enumerate(win_event_viewer.get_event_filter_generator("System",
                                                                                   target_computer=None,
                                                                                   all_requirements=True,
                                                                                   hour=3,
                                                                                   eventID=37)):

            self.assertEqual(event.get('timeGenerated')[3], 3)
            self.assertEqual(event.get('eventID'), 37)

            if number == MAX_EVENT_LOOK_UP:
                break

    def test_all_get_event_filter_generator(self):
        for number, event in enumerate(win_event_viewer.get_event_filter_generator("System",
                                                                                   target_computer=None,
                                                                                   all_requirements=False,
                                                                                   hour=3,
                                                                                   eventID=37)):

            self.assertTrue(event.get('timeGenerated')[3] == 3 or event.get('eventID') == 37)

            if number == MAX_EVENT_LOOK_UP:
                break

    @staticmethod
    def test_log_event():
        '''
        info: does not check for event because
         * the log can be slow to update
         * the log can be cleared at anytime
         * I dont want to add a flaky test
        :return:
        '''

        win_event_viewer.log_event('salt_test', event_id=117)

    def test_get_number_of_events(self):
        event_count = win_event_viewer.get_number_of_events("Application", target_computer=None)
        self.assertIsInstance(event_count, int)
        self.assertEqual(event_count, abs(event_count))
