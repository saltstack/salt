# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''

# Import Python Libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath
from salt.exceptions import SaltInvocationError

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import timezone


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TimezoneTestCase(TestCase):
    '''
    Timezone test case
    '''
    TEST_TZ = 'UTC'

    def setUp(self):
        '''
        Setup test
        :return:
        '''
        timezone.__salt__ = {'file.sed': MagicMock(),
                             'cmd.run': MagicMock(),
                             'cmd.retcode': MagicMock(return_value=0)}
        timezone.__grains__ = {'os': 'unknown'}

    def tearDown(self):
        '''
        Teardown test
        :return:
        '''
        timezone.__salt__ = timezone.__grains__ = None

    @patch('salt.utils.which', MagicMock(return_value=False))
    def test_get_zone_centos(self):
        '''
        Test CentOS is recognized
        :return:
        '''
        timezone.__grains__['os'] = 'centos'
        with patch('salt.modules.timezone._get_zone_etc_localtime', MagicMock(return_value=self.TEST_TZ)):
            assert timezone.get_zone() == self.TEST_TZ

    @patch('salt.utils.which', MagicMock(return_value=False))
    def test_get_zone_os_family_rh_suse(self):
        '''
        Test RedHat and Suse are recognized
        :return:
        '''
        for osfamily in ['RedHat', 'Suse']:
            timezone.__grains__['os_family'] = [osfamily]
            with patch('salt.modules.timezone._get_zone_sysconfig', MagicMock(return_value=self.TEST_TZ)):
                assert timezone.get_zone() == self.TEST_TZ

    @patch('salt.utils.which', MagicMock(return_value=False))
    def test_get_zone_os_family_debian_gentoo(self):
        '''
        Test Debian and Gentoo are recognized
        :return:
        '''
        for osfamily in ['Debian', 'Gentoo']:
            timezone.__grains__['os_family'] = [osfamily]
            with patch('salt.modules.timezone._get_zone_etc_timezone', MagicMock(return_value=self.TEST_TZ)):
                assert timezone.get_zone() == self.TEST_TZ

    @patch('salt.utils.which', MagicMock(return_value=False))
    def test_get_zone_os_family_allbsd_nilinuxrt(self):
        '''
        Test *BSD and NILinuxRT are recognized
        :return:
        '''
        for osfamily in ['FreeBSD', 'OpenBSD', 'NetBSD', 'NILinuxRT']:
            timezone.__grains__['os_family'] = osfamily
            with patch('salt.modules.timezone._get_zone_etc_localtime', MagicMock(return_value=self.TEST_TZ)):
                assert timezone.get_zone() == self.TEST_TZ

    @patch('salt.utils.which', MagicMock(return_value=False))
    def test_get_zone_os_family_slowlaris(self):
        '''
        Test Slowlaris is recognized
        :return:
        '''
        timezone.__grains__['os_family'] = ['Solaris']
        with patch('salt.modules.timezone._get_zone_solaris', MagicMock(return_value=self.TEST_TZ)):
            assert timezone.get_zone() == self.TEST_TZ

    @patch('salt.utils.which', MagicMock(return_value=False))
    def test_get_zone_os_family_aix(self):
        '''
        Test IBM AIX is recognized
        :return:
        '''
        timezone.__grains__['os_family'] = ['AIX']
        with patch('salt.modules.timezone._get_zone_aix', MagicMock(return_value=self.TEST_TZ)):
            assert timezone.get_zone() == self.TEST_TZ

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    def test_set_zone_redhat(self):
        '''
        Test zone set on RH series
        :return:
        '''
        timezone.__grains__['os_family'] = ['RedHat']
        assert timezone.set_zone(self.TEST_TZ)
        name, args, kwargs = timezone.__salt__['file.sed'].mock_calls[0]
        assert args == ('/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="UTC"')

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    def test_set_zone_suse(self):
        '''
        Test zone set on SUSE series
        :return:
        '''
        timezone.__grains__['os_family'] = ['Suse']
        assert timezone.set_zone(self.TEST_TZ)
        name, args, kwargs = timezone.__salt__['file.sed'].mock_calls[0]
        assert args == ('/etc/sysconfig/clock', '^TIMEZONE=.*', 'TIMEZONE="UTC"')

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    def test_set_zone_gentoo(self):
        '''
        Test zone set on Gentoo series
        :return:
        '''
        timezone.__grains__['os_family'] = ['Gentoo']
        _fopen = MagicMock(return_value=MagicMock(spec=file))
        with patch('salt.utils.fopen', _fopen):
            assert timezone.set_zone(self.TEST_TZ)
            name, args, kwargs = _fopen.mock_calls[0]
            assert args == ('/etc/timezone', 'w')
            name, args, kwargs = _fopen.return_value.__enter__.return_value.write.mock_calls[0]
            assert args == ('UTC',)

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    def test_set_zone_debian(self):
        '''
        Test zone set on Debian series
        :return:
        '''
        timezone.__grains__['os_family'] = ['Debian']
        _fopen = MagicMock(return_value=MagicMock(spec=file))
        with patch('salt.utils.fopen', _fopen):
            assert timezone.set_zone(self.TEST_TZ)
            name, args, kwargs = _fopen.mock_calls[0]
            assert args == ('/etc/timezone', 'w')
            name, args, kwargs = _fopen.return_value.__enter__.return_value.write.mock_calls[0]
            assert args == ('UTC',)

    @patch('salt.utils.which', MagicMock(return_value=True))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    def test_get_hwclock_timedate_utc(self):
        '''
        Test get hwclock UTC/localtime
        :return:
        '''
        with patch('salt.modules.timezone._timedatectl', MagicMock(return_value={'stdout': 'rtc in local tz'})):
            assert timezone.get_hwclock() == 'UTC'
        with patch('salt.modules.timezone._timedatectl', MagicMock(return_value={'stdout': 'rtc in local tz:yes'})):
            assert timezone.get_hwclock() == 'localtime'

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    def test_get_hwclock_suse(self):
        '''
        Test get hwclock on SUSE
        :return:
        '''
        timezone.__grains__['os_family'] = ['Suse']
        timezone.get_hwclock()
        name, args, kwarg = timezone.__salt__['cmd.run'].mock_calls[0]
        assert args == (['tail', '-n', '1', '/etc/adjtime'],)
        assert kwarg == {'python_shell': False}

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    def test_get_hwclock_redhat(self):
        '''
        Test get hwclock on RedHat
        :return:
        '''
        timezone.__grains__['os_family'] = ['RedHat']
        timezone.get_hwclock()
        name, args, kwarg = timezone.__salt__['cmd.run'].mock_calls[0]
        assert args == (['tail', '-n', '1', '/etc/adjtime'],)
        assert kwarg == {'python_shell': False}

    def _test_get_hwclock_debian(self):  # TODO: Enable this when testing environment is working properly
        '''
        Test get hwclock on Debian
        :return:
        '''
        with patch('salt.utils.which', MagicMock(return_value=False)):
            with patch('os.path.exists', MagicMock(return_value=True)):
                with patch('os.unlink', MagicMock()):
                    with patch('os.symlink', MagicMock()):
                        timezone.__grains__['os_family'] = ['Debian']
                        timezone.get_hwclock()
                        name, args, kwarg = timezone.__salt__['cmd.run'].mock_calls[0]
                        assert args == (['tail', '-n', '1', '/etc/adjtime'],)
                        assert kwarg == {'python_shell': False}

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    def test_get_hwclock_solaris(self):
        '''
        Test get hwclock on Solaris
        :return:
        '''
        # Incomplete
        timezone.__grains__['os_family'] = ['Solaris']
        assert timezone.get_hwclock() == 'UTC'
        _fopen = MagicMock(return_value=MagicMock(spec=file))
        with patch('salt.utils.fopen', _fopen):
            assert timezone.get_hwclock() == 'localtime'

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    def test_get_hwclock_aix(self):
        '''
        Test get hwclock on AIX
        :return:
        '''
        # Incomplete
        hwclock = 'localtime'
        if not os.path.isfile('/etc/environment'):
            hwclock = 'UTC'
        timezone.__grains__['os_family'] = ['AIX']
        assert timezone.get_hwclock() == hwclock

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    def test_set_hwclock_aix(self):
        '''
        Test set hwclock on AIX
        :return:
        '''
        timezone.__grains__['os_family'] = ['AIX']
        with self.assertRaises(SaltInvocationError):
            assert timezone.set_hwclock('forty two')
        assert timezone.set_hwclock('UTC')

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    @patch('salt.modules.timezone.get_zone', MagicMock(return_value='TEST_TIMEZONE'))
    def test_set_hwclock_solaris(self):
        '''
        Test set hwclock on Solaris
        :return:
        '''
        timezone.__grains__['os_family'] = ['Solaris']
        timezone.__grains__['cpuarch'] = 'x86'

        with self.assertRaises(SaltInvocationError):
            assert timezone.set_hwclock('forty two')
        assert timezone.set_hwclock('UTC')
        name, args, kwargs = timezone.__salt__['cmd.retcode'].mock_calls[0]
        assert args == (['rtc', '-z', 'GMT'],)
        assert kwargs == {'python_shell': False}

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    @patch('salt.modules.timezone.get_zone', MagicMock(return_value='TEST_TIMEZONE'))
    def test_set_hwclock_arch(self):
        '''
        Test set hwclock on arch
        :return:
        '''
        timezone.__grains__['os_family'] = ['Arch']

        assert timezone.set_hwclock('UTC')
        name, args, kwargs = timezone.__salt__['cmd.retcode'].mock_calls[0]
        assert args == (['timezonectl', 'set-local-rtc', 'false'],)
        assert kwargs == {'python_shell': False}

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    @patch('salt.modules.timezone.get_zone', MagicMock(return_value='TEST_TIMEZONE'))
    def test_set_hwclock_redhat(self):
        '''
        Test set hwclock on RedHat
        :return:
        '''
        timezone.__grains__['os_family'] = ['RedHat']

        assert timezone.set_hwclock('UTC')
        name, args, kwargs = timezone.__salt__['file.sed'].mock_calls[0]
        assert args == ('/etc/sysconfig/clock', '^ZONE=.*', 'ZONE="TEST_TIMEZONE"')

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    @patch('salt.modules.timezone.get_zone', MagicMock(return_value='TEST_TIMEZONE'))
    def test_set_hwclock_suse(self):
        '''
        Test set hwclock on SUSE
        :return:
        '''
        timezone.__grains__['os_family'] = ['Suse']

        assert timezone.set_hwclock('UTC')
        name, args, kwargs = timezone.__salt__['file.sed'].mock_calls[0]
        assert args == ('/etc/sysconfig/clock', '^TIMEZONE=.*', 'TIMEZONE="TEST_TIMEZONE"')

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    @patch('salt.modules.timezone.get_zone', MagicMock(return_value='TEST_TIMEZONE'))
    def test_set_hwclock_debian(self):
        '''
        Test set hwclock on Debian
        :return:
        '''
        timezone.__grains__['os_family'] = ['Debian']

        assert timezone.set_hwclock('UTC')
        name, args, kwargs = timezone.__salt__['file.sed'].mock_calls[0]
        assert args == ('/etc/default/rcS', '^UTC=.*', 'UTC=yes')

        assert timezone.set_hwclock('localtime')
        name, args, kwargs = timezone.__salt__['file.sed'].mock_calls[1]
        assert args == ('/etc/default/rcS', '^UTC=.*', 'UTC=no')

    @patch('salt.utils.which', MagicMock(return_value=False))
    @patch('os.path.exists', MagicMock(return_value=True))
    @patch('os.unlink', MagicMock())
    @patch('os.symlink', MagicMock())
    @patch('salt.modules.timezone.get_zone', MagicMock(return_value='TEST_TIMEZONE'))
    def test_set_hwclock_gentoo(self):
        '''
        Test set hwclock on Gentoo
        :return:
        '''
        timezone.__grains__['os_family'] = ['Gentoo']

        with self.assertRaises(SaltInvocationError):
            timezone.set_hwclock('forty two')

        timezone.set_hwclock('UTC')
        name, args, kwargs = timezone.__salt__['file.sed'].mock_calls[0]
        assert args == ('/etc/conf.d/hwclock', '^clock=.*', 'clock="UTC"')

        timezone.set_hwclock('localtime')
        name, args, kwargs = timezone.__salt__['file.sed'].mock_calls[1]
        assert args == ('/etc/conf.d/hwclock', '^clock=.*', 'clock="local"')
