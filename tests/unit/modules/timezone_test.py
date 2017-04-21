# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Bo Maryniuk <bo@suse.de>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

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
        timezone.__salt__ = {'file.sed': MagicMock()}
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
        timezone.__salt__
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
        timezone.__grains__['os_family'] = ['SUSE']
        timezone.__salt__
        assert timezone.set_zone(self.TEST_TZ)
        name, args, kwargs = timezone.__salt__['file.sed'].mock_calls[0]
        assert args == ('/etc/sysconfig/clock', '^TIMEZONE=.*', 'TIMEZONE="UTC"')
