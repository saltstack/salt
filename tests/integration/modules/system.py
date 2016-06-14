# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import os
import hashlib

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import (
    destructiveTest,
    ensure_in_syspath,
    requires_system_grains
)

ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils
import time
import datetime

class SystemModuleTest(integration.ModuleCase):
    '''
    Validate the date/time functions in the system module
    '''
    fmt_str = "%Y-%m-%d %H:%M:%S"

    def _save_time(self):
        self._orig_time = datetime.datetime.now()

    def _set_time(self, new_time, posix=None, utc=None):
        t = new_time.timetuple()[:6]
        return self.run_function('system.set_system_date_time', t,
                posix=posix, utc=utc)

    def _restore_time(self, utc=None):
        if utc is True:
            t = datetime.datetime.utcnow()
        else:
            t = datetime.datetime.now()
        test_timediff = t - self._fake_time
        now = test_timediff + self._orig_time
        self._set_time(now)

    def _same_times(self, t1, t2, seconds_diff=1):
        return abs(t1 - t2) < datetime.timedelta(seconds=seconds_diff)

    def test_get_system_date_time(self):
        '''
        Test we are able to get the correct time
        '''
        t1 = datetime.datetime.now()
        res = self.run_function('system.get_system_date_time')
        t2 = datetime.datetime.strptime(res, self.fmt_str)
        msg = ("Difference in times is too large. Now: {} Fake: {}"
                .format(t1, t2))
        self.assertTrue(self._same_times(t1, t2),msg=msg)

    def test_get_system_date_time_utc(self):
        '''
        Test we are able to get the correct time with utc
        '''
        t1 = datetime.datetime.utcnow()
        res = self.run_function('system.get_system_date_time', utc=True)
        t2 = datetime.datetime.strptime(res, self.fmt_str)
        msg = ("Difference in times is too large. Now: {} Fake: {}"
                .format(t1, t2))
        self.assertTrue(self._same_times(t1, t2), msg=msg)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date_time(self):
        '''
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        '''
        self._fake_time = datetime.datetime.strptime("1981-02-03 04:05:06",
                self.fmt_str)

        self._save_time()
        self._set_time(self._fake_time)

        time_now = datetime.datetime.now()
        msg = ("Difference in times is too large. Now: {} Fake: {}"
                .format(time_now, self._fake_time))
        self.assertTrue(self._same_times(time_now, self._fake_time), msg=msg)

        self._restore_time()

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date_time_utc(self):
        '''
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        '''
        self._fake_time = datetime.datetime.strptime("1981-02-03 04:05:06",
                self.fmt_str)

        self._save_time()
        result = self._set_time(self._fake_time, utc=True)

        time_now = datetime.datetime.utcnow()
        msg = ("Difference in times is too large. Now: {} Fake: {}"
                .format(time_now, self._fake_time))
        self.assertTrue(result and self._same_times(time_now,self._fake_time),
                msg=msg)

        self._restore_time(utc=True)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date_time_posix(self):
        '''
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        '''
        self._fake_time = datetime.datetime.strptime("1981-02-03 04:05:06",
                self.fmt_str)

        self._save_time()
        result = self._set_time(self._fake_time, posix=True)

        time_now = datetime.datetime.now()
        msg = ("Difference in times is too large. Now: {} Fake: {}"
                .format(time_now, self._fake_time))
        self.assertTrue(result and self._same_times(time_now, self._fake_time,
            seconds_diff=60), msg=msg) # posix only enables setting to minute

        self._restore_time()

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date_time_posix_utc(self):
        '''
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        '''
        self._fake_time = datetime.datetime.strptime("1981-02-03 04:05:06",
                self.fmt_str)

        self._save_time()
        result = self._set_time(self._fake_time, posix=True, utc=True)

        time_now = datetime.datetime.utcnow()
        msg = ("Difference in times is too large. Now: {} Fake: {}"
                .format(time_now, self._fake_time))
        self.assertTrue(result and self._same_times(time_now, self._fake_time,
            seconds_diff=60), msg=msg) # posix only enables setting to minute

        self._restore_time(utc=True)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_time(self):
        '''
        Test setting the system time without adjusting the date.
        '''
        self._fake_time = datetime.datetime.combine(datetime.date.today(),
                datetime.time(4,5,0))

        self._save_time()

        result = self.run_function('system.set_system_time', ["04:05:00"])

        time_now = datetime.datetime.now()
        msg = ("Difference in times is too large. Now: {} Fake: {}"
                .format(time_now, self._fake_time))

        self.assertTrue(result)
        self.assertTrue(time_now.hour == 4 and
                time_now.minute == 5 and
                (time_now.second < 10), msg=msg)

        self._restore_time()

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date(self):
        '''
        Test setting the system date without adjusting the time.
        '''
        self._fake_time = datetime.datetime.combine(
                datetime.datetime(2000, 12, 25), datetime.datetime.now().time())

        self._save_time()

        result = self.run_function('system.set_system_date', ["2000-12-25"])

        time_now = datetime.datetime.now()
        msg = ("Difference in times is too large. Now: {} Fake: {}"
                .format(time_now, self._fake_time))

        self.assertTrue(result)
        self.assertTrue(time_now.year == 2000 and
                time_now.day == 25 and
                time_now.month == 12 and
                time_now.hour == self._orig_time.hour and
                time_now.minute == self._orig_time.minute
                , msg=msg)

        self._restore_time()

if __name__ == '__main__':
    from integration import run_tests
    run_tests(SystemModuleTest)
