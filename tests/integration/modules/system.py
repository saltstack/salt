# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import datetime
import os

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath
)

ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils
import salt.states.file


@skipIf(not salt.utils.is_linux(), 'These tests can only be run on linux')
class SystemModuleTest(integration.ModuleCase):
    '''
    Validate the date/time functions in the system module
    '''
    fmt_str = "%Y-%m-%d %H:%M:%S"

    def __init__(self, arg):
        super(self.__class__, self).__init__(arg)
        self._orig_time = None
        self._machine_info = True

    def setUp(self):
        super(SystemModuleTest, self).setUp()
        os_grain = self.run_function('grains.item', ['kernel'])
        if os_grain['kernel'] not in 'Linux':
            self.skipTest(
                'Test not applicable to \'{kernel}\' kernel'.format(
                    **os_grain
                )
            )
        if self.run_function('service.available', ['systemd-timesyncd']):
            self.run_function('service.stop', ['systemd-timesyncd'])

    def tearDown(self):
        if self._orig_time is not None:
            self._restore_time()
        self._orig_time = None
        if self._machine_info is not True:
            self._restore_machine_info()
        self._machine_info = True
        if self.run_function('service.available', ['systemd-timesyncd']):
            self.run_function('service.start', ['systemd-timesyncd'])

    def _save_time(self):
        self._orig_time = datetime.datetime.utcnow()

    def _set_time(self, new_time, offset=None):
        t = new_time.timetuple()[:6]
        t += (offset,)
        return self.run_function('system.set_system_date_time', t)

    def _restore_time(self):
        result = self._set_time(self._orig_time, "+0000")
        self.assertTrue(result, msg="Unable to restore time properly")

    def _same_times(self, t1, t2, seconds_diff=2):
        '''
        Helper function to check if two datetime objects
        are close enough to the same time.
        '''
        return abs(t1 - t2) < datetime.timedelta(seconds=seconds_diff)

    def _save_machine_info(self):
        if os.path.isfile('/etc/machine-info'):
            with salt.utils.fopen('/etc/machine-info', 'r') as mach_info:
                self._machine_info = mach_info.read()
        else:
            self._machine_info = False

    def _restore_machine_info(self):
        if self._machine_info is not False:
            with salt.utils.fopen('/etc/machine-info', 'w') as mach_info:
                mach_info.write(self._machine_info)
        else:
            self.run_function('file.remove', ['/etc/machine-info'])

    def test_get_system_date_time(self):
        '''
        Test we are able to get the correct time
        '''
        t1 = datetime.datetime.now()
        res = self.run_function('system.get_system_date_time')
        t2 = datetime.datetime.strptime(res, self.fmt_str)
        msg = ("Difference in times is too large. Now: {0} Fake: {1}"
               .format(t1, t2))
        self.assertTrue(self._same_times(t1, t2), msg=msg)

    def test_get_system_date_time_utc(self):
        '''
        Test we are able to get the correct time with utc
        '''
        t1 = datetime.datetime.utcnow()
        res = self.run_function('system.get_system_date_time',
                                utc_offset="+0000")
        t2 = datetime.datetime.strptime(res, self.fmt_str)
        msg = ("Difference in times is too large. Now: {0} Fake: {1}"
               .format(t1, t2))
        self.assertTrue(self._same_times(t1, t2), msg=msg)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date_time(self):
        '''
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        '''
        cmp_time = datetime.datetime.strptime("1981-02-03 04:05:06",
                                              self.fmt_str)

        self._save_time()
        result = self._set_time(cmp_time)

        time_now = datetime.datetime.now()
        msg = ("Difference in times is too large. Now: {0} Fake: {1}"
               .format(time_now, cmp_time))
        self.assertTrue(result and self._same_times(time_now, cmp_time),
                        msg=msg)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date_time_utc(self):
        '''
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        '''
        cmp_time = datetime.datetime.strptime("1981-02-03 04:05:06", self.fmt_str)

        self._save_time()
        result = self._set_time(cmp_time, offset="+0000")

        time_now = datetime.datetime.utcnow()
        msg = ("Difference in times is too large. Now: {0} Fake: {1}"
               .format(time_now, cmp_time))
        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date_time_utcoffset_east(self):
        '''
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        '''
        cmp_time = datetime.datetime.strptime("1981-02-03 11:05:06",
                                              self.fmt_str)
        offset_str = "-0700"
        time_to_set = datetime.datetime.strptime("1981-02-03 04:05:06",
                                                 self.fmt_str)

        self._save_time()

        result = self._set_time(time_to_set, offset=offset_str)

        time_now = datetime.datetime.utcnow()
        msg = ("Difference in times is too large. Now: {0} Fake: {1}"
               .format(time_now, cmp_time))
        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date_time_utcoffset_west(self):
        '''
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        '''
        cmp_time = datetime.datetime.strptime("1981-02-03 02:05:06",
                                                     self.fmt_str)
        offset_str = "+0200"
        time_to_set = datetime.datetime.strptime("1981-02-03 04:05:06",
                                                 self.fmt_str)

        self._save_time()
        result = self._set_time(time_to_set, offset=offset_str)

        time_now = datetime.datetime.utcnow()
        msg = ("Difference in times is too large. Now: {0} Fake: {1}"
               .format(time_now, cmp_time))
        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_time(self):
        '''
        Test setting the system time without adjusting the date.
        '''
        cmp_time = datetime.datetime.now().replace(hour=10, minute=5, second=0)
        self._save_time()

        result = self.run_function('system.set_system_time', ["10:05:00"])

        time_now = datetime.datetime.now()
        msg = ("Difference in times is too large. Now: {0} Fake: {1}"
               .format(time_now, cmp_time))

        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date(self):
        '''
        Test setting the system date without adjusting the time.
        '''
        cmp_time = datetime.datetime.now().replace(year=2000, month=12, day=25)

        self._save_time()
        result = self.run_function('system.set_system_date', ["2000-12-25"])

        time_now = datetime.datetime.now()
        msg = ("Difference in times is too large. Now: {0} Fake: {1}"
               .format(time_now, cmp_time))

        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)

    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_get_computer_desc(self):
        '''
        Test getting the system hostname
        '''
        res = self.run_function('system.get_computer_desc')

        hostname_cmd = salt.utils.which('hostnamectl')
        if hostname_cmd:
            desc = self.run_function('cmd.run', ["hostnamectl status --pretty"])
            self.assertEqual(res, desc)
        else:
            if not os.path.isfile('/etc/machine-info'):
                self.assertFalse(res)
            else:
                with salt.utils.fopen('/etc/machine-info', 'r') as mach_info:
                    data = mach_info.read()
                    self.assertIn(res, data.decode('string_escape'))

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_computer_desc(self):
        '''
        Test setting the system hostname
        '''
        self._save_machine_info()
        desc = "test"
        ret = self.run_function('system.set_computer_desc', [desc])
        computer_desc = self.run_function('system.get_computer_desc')

        self.assertTrue(ret)
        self.assertIn(desc, computer_desc)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(SystemModuleTest)
