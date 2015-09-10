# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    mock_open,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
import salt.utils
from salt.modules import timezone
import os
from salt.exceptions import CommandExecutionError, SaltInvocationError


# Globals
timezone.__grains__ = {}
timezone.__salt__ = {}
timezone.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class TimezoneTestCase(TestCase):
    '''
    Test cases for salt.modules.timezone
    '''
    def test_get_zone(self):
        '''
        Test to get current timezone (i.e. America/Denver)
        '''
        mock = MagicMock(side_effect=['Time zone: A', 'A'])
        with patch.object(salt.utils, 'which', return_value=True):
            with patch.dict(timezone.__salt__, {'cmd.run': mock}):
                self.assertEqual(timezone.get_zone(), 'A')

                self.assertRaises(CommandExecutionError, timezone.get_zone)

        with patch.object(salt.utils, 'which', return_value=False):
            file_data = '\n'.join(['#', 'A'])
            with patch('salt.utils.fopen', mock_open(read_data=file_data),
                       create=True) as mfile:
                mfile.return_value.__iter__.return_value = file_data.splitlines()
                with patch.dict(timezone.__grains__, {'os_family': 'Debian',
                                                      'os': 'Debian'}):
                    self.assertEqual(timezone.get_zone(), '#\nA')

                with patch.dict(timezone.__grains__, {'os_family': 'Gentoo',
                                                      'os': 'Gentoo'}):
                    self.assertEqual(timezone.get_zone(), '')

            with patch.dict(timezone.__grains__, {'os_family': 'FreeBSD',
                                                  'os': 'FreeBSD'}):
                zone = 'America/Denver'
                linkpath = '/usr/share/zoneinfo/' + zone
                with patch.object(os, 'readlink', return_value=linkpath):
                    self.assertEqual(timezone.get_zone(), zone)

            with patch.dict(timezone.__grains__, {'os_family': 'Solaris',
                                                  'os': 'Solaris'}):
                fl_data = 'TZ=Foo\n'
                with patch('salt.utils.fopen',
                           mock_open(read_data=fl_data)) as mfile:
                    mfile.return_value.__iter__.return_value = [fl_data]
                    self.assertEqual(timezone.get_zone(), 'Foo')

    def test_get_zonecode(self):
        '''
        Test to get current timezone (i.e. PST, MDT, etc)
        '''
        with patch.dict(timezone.__salt__, {'cmd.run':
                                            MagicMock(return_value='A')}):
            self.assertEqual(timezone.get_zonecode(), 'A')

    def test_get_offset(self):
        '''
        Test to get current numeric timezone offset from UCT (i.e. -0700)
        '''
        with patch.dict(timezone.__salt__, {'cmd.run':
                                            MagicMock(return_value='A')}):
            self.assertEqual(timezone.get_offset(), 'A')

    def test_set_zone(self):
        '''
        Test to unlinks, then symlinks /etc/localtime to the set timezone.
        '''
        ret = ('Zone does not exist: /usr/share/lib/zoneinfo/timezone')
        mock = MagicMock(side_effect=[False, True, True])
        with patch.dict(timezone.__grains__, {'os_family': 'Solaris'}):
            with patch.object(os.path, 'exists', mock):
                self.assertEqual(timezone.set_zone('timezone'), ret)

                with patch.object(os, 'unlink', return_value=None):
                    with patch.dict(timezone.__salt__,
                                    {'file.sed':
                                     MagicMock(return_value=None)}):
                        self.assertTrue(timezone.set_zone('timezone'))

    def test_zone_compare(self):
        '''
        Test to checks the hash sum between the given timezone, and the
        one set in /etc/localtime.
        '''
        with patch.dict(timezone.__grains__, {'os_family': 'Solaris'}):
            self.assertEqual(timezone.zone_compare('timezone'),
                             'Not implemented for Solaris family')

        with patch.dict(timezone.__grains__, {'os_family': 'Sola'}):
            with patch.object(os.path, 'exists', return_value=False):
                self.assertEqual(timezone.zone_compare('timezone'),
                                 'Error: /etc/localtime does not exist.')

        with patch.object(os.path, 'exists', return_value=True):
            with patch.dict(timezone.__grains__, {'os_family': 'Sola'}):
                with patch.dict(timezone.__opts__, {'hash_type': 'md5'}):
                    with patch.object(salt.utils, 'get_hash',
                                      side_effect=IOError('foo')):
                        self.assertRaises(SaltInvocationError,
                                          timezone.zone_compare, 't')

                    with patch.object(salt.utils, 'get_hash',
                                      side_effect=['A', IOError('foo')]):
                        self.assertRaises(CommandExecutionError,
                                          timezone.zone_compare, 't')

                    with patch.object(salt.utils, 'get_hash',
                                      side_effect=['A', 'A']):
                        self.assertTrue(timezone.zone_compare('timezone'))

                    with patch.object(salt.utils, 'get_hash',
                                      side_effect=['A', 'B']):
                        self.assertFalse(timezone.zone_compare('timezone'))

    def test_get_hwclock(self):
        '''
        Test to get current hardware clock setting (UTC or localtime)
        '''
        with patch.object(salt.utils, 'which', return_value=True):
            with patch.dict(timezone.__salt__,
                            {'cmd.run':
                             MagicMock(return_value='rtc in local tz:yes\n')}):
                self.assertEqual(timezone.get_hwclock(), 'localtime')

            with patch.dict(timezone.__salt__,
                            {'cmd.run':
                             MagicMock(return_value='rtc in local tz:No\n')}):
                self.assertEqual(timezone.get_hwclock(), 'UTC')

            with patch.dict(timezone.__salt__,
                            {'cmd.run':
                             MagicMock(return_value='rtc')}):
                self.assertRaises(CommandExecutionError, timezone.get_hwclock)

        with patch.object(salt.utils, 'which', return_value=False):
            with patch.dict(timezone.__grains__, {'os_family': 'RedHat'}):
                with patch.dict(timezone.__salt__,
                                {'cmd.run':
                                 MagicMock(return_value='A')}):
                    self.assertEqual(timezone.get_hwclock(), 'A')

            with patch.dict(timezone.__grains__, {'os_family': 'Suse'}):
                with patch.dict(timezone.__salt__,
                                {'cmd.run':
                                 MagicMock(return_value='A')}):
                    self.assertEqual(timezone.get_hwclock(), 'A')

            with patch.dict(timezone.__grains__, {'os_family': 'Debian'}):
                fl_data = 'UTC=yes\n'
                with patch('salt.utils.fopen',
                           mock_open(read_data=fl_data)) as mfile:
                    mfile.return_value.__iter__.return_value = [fl_data]
                    self.assertEqual(timezone.get_hwclock(), 'UTC')

                fl_data = 'UTC=no\n'
                with patch('salt.utils.fopen',
                           mock_open(read_data=fl_data)) as mfile:
                    mfile.return_value.__iter__.return_value = [fl_data]
                    self.assertEqual(timezone.get_hwclock(), 'localtime')

            with patch.dict(timezone.__grains__, {'os_family': 'Gentoo'}):
                fl_data = 'clock=UTC\n'
                with patch('salt.utils.fopen',
                           mock_open(read_data=fl_data)) as mfile:
                    mfile.return_value.__iter__.return_value = [fl_data]
                    self.assertEqual(timezone.get_hwclock(), 'UTC')

        mock = MagicMock(return_value=True)
        with patch.object(os.path, 'isfile', mock):
            fl_data = 'zone_info=GMT'
            with patch('salt.utils.fopen',
                       mock_open(read_data=fl_data),
                       create=True) as mfile:
                mfile.return_value.__iter__.return_value = fl_data.splitlines()
                with patch.object(salt.utils, 'which', return_value=False):
                    with patch.dict(timezone.__grains__,
                                    {'os_family': 'Solaris'}):
                        self.assertEqual(timezone.get_hwclock(), 'UTC')

        mock = MagicMock(return_value=True)
        with patch.object(os.path, 'isfile', mock):
            fl_data = 'A=GMT'
            with patch('salt.utils.fopen',
                       mock_open(read_data=fl_data),
                       create=True) as mfile:
                mfile.return_value.__iter__.return_value = fl_data.splitlines()
                with patch.object(salt.utils, 'which', return_value=False):
                    with patch.dict(timezone.__grains__,
                                    {'os_family': 'Solaris'}):
                        self.assertEqual(timezone.get_hwclock(), 'localtime')

        with patch.object(salt.utils, 'which', return_value=False):
            with patch.dict(timezone.__grains__, {'os_family': 'Solaris'}):
                mock = MagicMock(return_value=False)
                with patch.object(os.path, 'isfile', mock):
                    self.assertEqual(timezone.get_hwclock(), 'UTC')

    def test_set_hwclock(self):
        '''
        Test to sets the hardware clock to be either UTC or localtime
        '''
        zone = 'America/Denver'
        with patch.object(timezone, 'get_zone', return_value=zone):

            with patch.dict(timezone.__grains__, {'os_family': 'Solaris',
                                                  'cpuarch': 'sparc'}):
                self.assertRaises(
                    SaltInvocationError,
                    timezone.set_hwclock,
                    'clock'
                )
                self.assertRaises(
                    SaltInvocationError,
                    timezone.set_hwclock,
                    'localtime'
                )

            with patch.dict(timezone.__grains__,
                            {'os_family': 'DoesNotMatter'}):
                with patch.object(os.path, 'exists', return_value=False):
                    self.assertRaises(
                        CommandExecutionError,
                        timezone.set_hwclock,
                        'UTC'
                    )

if __name__ == '__main__':
    from integration import run_tests
    run_tests(TimezoneTestCase, needs_daemon=False)
