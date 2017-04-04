# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import
import datetime
import logging
import os
import signal
import subprocess

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.helpers import destructiveTest

# Import salt libs
import salt.utils
import salt.states.file
from salt.ext.six.moves import range

log = logging.getLogger(__name__)


@skipIf(not salt.utils.is_linux(), 'These tests can only be run on linux')
class SystemModuleTest(ModuleCase):
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

    def _same_times(self, t1, t2, seconds_diff=30):
        '''
        Helper function to check if two datetime objects
        are close enough to the same time.
        '''
        return abs(t1 - t2) < datetime.timedelta(seconds=seconds_diff)

    def _hwclock_has_compare(self):
        '''
        Some builds of hwclock don't include the `--compare` function
        needed to test hw/sw clock synchronization. Returns false on
        systems where it's not present so that we can skip the
        comparison portion of the test.
        '''
        res = self.run_function('cmd.run_all', cmd='hwclock -h')
        return res['retcode'] == 0 and res['stdout'].find('--compare') > 0

    def _test_hwclock_sync(self):
        '''
        Check that hw and sw clocks are sync'd.
        '''
        if not self.run_function('system.has_settable_hwclock'):
            return None
        if not self._hwclock_has_compare():
            return None

        class CompareTimeout(BaseException):
            pass

        def _alrm_handler(sig, frame):
            log.warning('hwclock --compare failed to produce output after 3 seconds')
            raise CompareTimeout

        for _ in range(2):
            try:
                orig_handler = signal.signal(signal.SIGALRM, _alrm_handler)
                signal.alarm(3)
                rpipeFd, wpipeFd = os.pipe()
                log.debug('Comparing hwclock to sys clock')
                with os.fdopen(rpipeFd, "r") as rpipe:
                    with os.fdopen(wpipeFd, "w") as wpipe:
                        with salt.utils.fopen(os.devnull, "r") as nulFd:
                            p = subprocess.Popen(args=['hwclock', '--compare'],
                                stdin=nulFd, stdout=wpipeFd, stderr=subprocess.PIPE)
                            p.communicate()

                            # read header
                            rpipe.readline()

                            # read first time comparison
                            timeCompStr = rpipe.readline()

                            # stop
                            p.terminate()

                            timeComp = timeCompStr.split()
                            hwTime = float(timeComp[0])
                            swTime = float(timeComp[1])
                            diff = abs(hwTime - swTime)

                            self.assertTrue(diff <= 2.0,
                                msg=("hwclock difference too big: " + str(timeCompStr)))
                            break
            except CompareTimeout:
                p.terminate()
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, orig_handler)
        else:
            log.error('Failed to check hwclock sync')

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
        self.assertTrue(self._same_times(t1, t2, seconds_diff=2), msg=msg)

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
        self.assertTrue(self._same_times(t1, t2, seconds_diff=2), msg=msg)

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date_time(self):
        '''
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        '''
        self._save_time()
        cmp_time = datetime.datetime.now() - datetime.timedelta(days=7)
        result = self._set_time(cmp_time)
        time_now = datetime.datetime.now()

        msg = ("Difference in times is too large. Now: {0} Fake: {1}"
               .format(time_now, cmp_time))
        self.assertTrue(result and self._same_times(time_now, cmp_time),
                        msg=msg)
        self._test_hwclock_sync()

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date_time_utc(self):
        '''
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        '''
        self._save_time()
        cmp_time = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        result = self._set_time(cmp_time, offset="+0000")
        time_now = datetime.datetime.utcnow()

        msg = ("Difference in times is too large. Now: {0} Fake: {1}"
               .format(time_now, cmp_time))
        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)
        self._test_hwclock_sync()

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date_time_utcoffset_east(self):
        '''
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        '''
        self._save_time()
        cmp_time = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        # 25200 seconds = 7 hours
        time_to_set = cmp_time - datetime.timedelta(seconds=25200)
        result = self._set_time(time_to_set, offset='-0700')
        time_now = datetime.datetime.utcnow()

        msg = ("Difference in times is too large. Now: {0} Fake: {1}"
               .format(time_now, cmp_time))
        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)
        self._test_hwclock_sync()

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date_time_utcoffset_west(self):
        '''
        Test changing the system clock. We are only able to set it up to a
        resolution of a second so this test may appear to run in negative time.
        '''
        self._save_time()
        cmp_time = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        # 7200 seconds = 2 hours
        time_to_set = cmp_time + datetime.timedelta(seconds=7200)
        result = self._set_time(time_to_set, offset='+0200')
        time_now = datetime.datetime.utcnow()

        msg = ("Difference in times is too large. Now: {0} Fake: {1}"
               .format(time_now, cmp_time))
        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)
        self._test_hwclock_sync()

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
        self._test_hwclock_sync()

    @destructiveTest
    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_set_system_date(self):
        '''
        Test setting the system date without adjusting the time.
        '''
        cmp_time = datetime.datetime.now() - datetime.timedelta(days=7)

        self._save_time()
        result = self.run_function(
            'system.set_system_date',
            [cmp_time.strftime('%Y-%m-%d')]
        )

        time_now = datetime.datetime.now()
        msg = ("Difference in times is too large. Now: {0} Fake: {1}"
               .format(time_now, cmp_time))

        self.assertTrue(result)
        self.assertTrue(self._same_times(time_now, cmp_time), msg=msg)
        self._test_hwclock_sync()

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

    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
    def test_has_hwclock(self):
        '''
        Verify platform has a settable hardware clock, if possible.
        '''
        if self.run_function('grains.get', ['os_family']) == 'NILinuxRT':
            self.assertTrue(self.run_function('system._has_settable_hwclock'))
            self.assertTrue(self._hwclock_has_compare())
