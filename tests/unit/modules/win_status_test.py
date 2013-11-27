# -*- coding: utf-8 -*-

# Import python libs
import new
import sys

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# wmi and pythoncom modules are platform specific...
wmi = new.module('wmi')
sys.modules['wmi'] = wmi

pythoncom = new.module('pythoncom')
sys.modules['pythoncom'] = pythoncom

from salttesting.mock import NO_MOCK, NO_MOCK_REASON, Mock, patch, call, ANY

if NO_MOCK is False:
    WMI = Mock()
    wmi.WMI = Mock(return_value=WMI)
    pythoncom.CoInitialize = Mock()
    pythoncom.CoUninitialize = Mock()

# This is imported late so mock can do it's job
import salt.modules.win_status as status


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TestProcsBase(TestCase):
    def __init__(self, *args, **kwargs):
        TestCase.__init__(self, *args, **kwargs)
        self.__processes = []

    def add_process(
            self,
            pid=100,
            cmd='cmd',
            name='name',
            user='user',
            user_domain='domain',
            get_owner_result=0):
        process = Mock()
        process.GetOwner = Mock(
            return_value=(user_domain, get_owner_result, user)
        )
        process.ProcessId = pid
        process.CommandLine = cmd
        process.Name = name
        self.__processes.append(process)

    def call_procs(self):
        WMI.win32_process = Mock(return_value=self.__processes)
        self.result = status.procs()


class TestProcsCount(TestProcsBase):
    def setUp(self):
        self.add_process(pid=100)
        self.add_process(pid=101)
        self.call_procs()

    def test_process_count(self):
        self.assertEqual(len(self.result), 2)

    def test_process_key_is_pid(self):
        self.assertSetEqual(set(self.result.keys()), set([100, 101]))


class TestProcsAttributes(TestProcsBase):
    def setUp(self):
        self._expected_name = 'name'
        self._expected_cmd = 'cmd'
        self._expected_user = 'user'
        self._expected_domain = 'domain'
        pid = 100
        self.add_process(
            pid=pid,
            cmd=self._expected_cmd,
            user=self._expected_user,
            user_domain=self._expected_domain,
            get_owner_result=0)
        self.call_procs()
        self.proc = self.result[pid]

    def test_process_cmd_is_set(self):
        self.assertEqual(self.proc['cmd'], self._expected_cmd)

    def test_process_name_is_set(self):
        self.assertEqual(self.proc['name'], self._expected_name)

    def test_process_user_is_set(self):
        self.assertEqual(self.proc['user'], self._expected_user)

    def test_process_user_domain_is_set(self):
        self.assertEqual(self.proc['user_domain'], self._expected_domain)


class TestProcsUnicodeAttributes(TestProcsBase):
    def setUp(self):
        unicode_str = u'\xc1'
        self.utf8str = unicode_str.encode('utf8')
        pid = 100
        self.add_process(
            pid=pid,
            user=unicode_str,
            user_domain=unicode_str,
            cmd=unicode_str,
            name=unicode_str)
        self.call_procs()
        self.proc = self.result[pid]

    def test_process_cmd_is_utf8(self):
        self.assertEqual(self.proc['cmd'], self.utf8str)

    def test_process_name_is_utf8(self):
        self.assertEqual(self.proc['name'], self.utf8str)

    def test_process_user_is_utf8(self):
        self.assertEqual(self.proc['user'], self.utf8str)

    def test_process_user_domain_is_utf8(self):
        self.assertEqual(self.proc['user_domain'], self.utf8str)


class TestProcsWMIGetOwnerAccessDeniedWorkaround(TestProcsBase):
    def setUp(self):
        self.expected_user = 'SYSTEM'
        self.expected_domain = 'NT AUTHORITY'
        self.add_process(pid=0, get_owner_result=2)
        self.add_process(pid=4, get_owner_result=2)
        self.call_procs()

    def test_user_is_set(self):
        self.assertEqual(self.result[0]['user'], self.expected_user)
        self.assertEqual(self.result[4]['user'], self.expected_user)

    def test_process_user_domain_is_set(self):
        self.assertEqual(self.result[0]['user_domain'], self.expected_domain)
        self.assertEqual(self.result[4]['user_domain'], self.expected_domain)


class TestProcsWMIGetOwnerErrorsAreLogged(TestProcsBase):
    def setUp(self):
        self.expected_error_code = 8
        self.add_process(get_owner_result=self.expected_error_code)

    def test_error_logged_if_process_get_owner_fails(self):
        with patch('salt.modules.win_status.log') as log:
            self.call_procs()
        log.warning.assert_called_once_with(ANY)
        self.assertIn(
            str(self.expected_error_code),
            log.warning.call_args[0][0]
        )


class TestEmptyCommandLine(TestProcsBase):
    def setUp(self):
        self.expected_error_code = 8
        pid = 100
        self.add_process(pid=pid, cmd=None)
        self.call_procs()
        self.proc = self.result[pid]

    def test_cmd_is_empty_string(self):
        self.assertEqual(self.proc['cmd'], '')


#class TestProcsComInitialization(TestProcsBase):
#    def setUp(self):
#        call_count = 5
#        for _ in range(call_count):
#            self.call_procs()
#        self.expected_calls = [call()] * call_count
#
#    def test_initialize_and_uninitialize_called(self):
#        pythoncom.CoInitialize.assert_has_calls(self.expected_calls)
#        pythoncom.CoUninitialize.assert_has_calls(self.expected_calls)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(
        [
            TestProcsCount,
            TestProcsAttributes,
            TestProcsUnicodeAttributes,
            TestProcsWMIGetOwnerErrorsAreLogged,
            TestProcsWMIGetOwnerAccessDeniedWorkaround,
        ],
        needs_daemon=False
    )
