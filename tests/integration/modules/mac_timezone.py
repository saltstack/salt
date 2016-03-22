# -*- coding: utf-8 -*-
'''
Integration tests for mac_timezone
'''

# Import python libs
from __future__ import absolute_import
from datetime import datetime

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, destructiveTest
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

USE_NETWORK_TIME = False
TIME_SERVER = 'time.apple.com'
TIME_ZONE = ''
CURRENT_DATE = ''
CURRENT_TIME = ''


class MacTimezoneModuleTest(integration.ModuleCase):
    '''
    Validate the mac_timezone module
    '''

    def setUp(self):
        '''
        Get current settings
        '''
        if not salt.utils.is_darwin():
            self.skipTest('Test only available on Mac OS X')

        if not salt.utils.which('systemsetup'):
            self.skipTest('Test requires systemsetup binary')

        if salt.utils.get_uid(salt.utils.get_user()) != 0:
            self.skipTest('Test requires root')

        USE_NETWORK_TIME = self.run_function('timezone.get_using_network_time')
        TIME_SERVER = self.run_function('timezone.get_time_server')
        TIME_ZONE = self.run_function('timezone.get_zone')
        CURRENT_DATE = self.run_function('timezone.get_date')
        CURRENT_TIME = self.run_function('timezone.get_time')

        self.run_function('timezone.set_using_network_time', [False])

    def tearDown(self):
        '''
        Reset to original settings
        '''
        self.run_function('timezone.set_time_server', [TIME_SERVER])
        self.run_function('timezone.set_using_network_time', [USE_NETWORK_TIME])
        self.run_function('timezone.set_zone', [TIME_ZONE])
        if not USE_NETWORK_TIME:
            self.run_function('timezone.set_date', [CURRENT_DATE])
            self.run_function('timezone.set_time', [CURRENT_TIME])

    @destructiveTest
    def test_get_set_date(self):
        '''
        Test timezone.get_date
        Test timezone.set_date
        '''
        # Correct Functionality
        self.assertTrue(self.run_function('timezone.set_date', ['2/20/2011']))
        self.assertEqual(self.run_function('timezone.get_date'), '2/20/2011')

        # Test bad date format
        self.assertEqual(
            self.run_function('timezone.set_date', ['13/12/2014']),
            'ERROR executing \'timezone.set_date\': '
            'Invalid Date/Time Format: 13/12/2014'
        )

    @destructiveTest
    def test_get_set_time(self):
        '''
        Test timezone.get_time
        Test timezone.set_time
        '''
        # Correct Functionality
        self.assertTrue(self.run_function('timezone.set_time', ['3:14']))
        new_time = self.run_function('timezone.get_time')
        new_time = datetime.strptime(new_time, '%H:%M:%S').strftime('%H:%M')
        self.assertEqual(new_time, '03:14')

        # Test bad time format
        self.assertEqual(
            self.run_function('timezone.set_time', ['3:71']),
            'ERROR executing \'timezone.set_time\': '
            'Invalid Date/Time Format: 3:71'
        )

    @destructiveTest
    def test_get_set_zone(self):
        '''
        Test timezone.get_zone
        Test timezone.set_zone
        '''
        # Correct Functionality
        self.assertTrue(self.run_function('timezone.set_zone',
                                          ['Pacific/Wake']))
        self.assertEqual(self.run_function('timezone.get_zone'), 'Pacific/Wake')

        # Test bad time zone
        self.assertEqual(
            self.run_function('timezone.set_zone', ['spongebob']),
            'ERROR executing \'timezone.set_zone\': '
            'Invalid Timezone: spongebob')

    @destructiveTest
    def test_get_offset(self):
        '''
        Test timezone.get_offset
        '''
        self.assertTrue(self.run_function('timezone.set_zone',
                                          ['Pacific/Wake']))
        self.assertEqual(self.run_function('timezone.get_offset'), '+1200')
        self.assertTrue(self.run_function('timezone.set_zone',
                                          ['America/Denver']))
        self.assertEqual(self.run_function('timezone.get_offset'), '-0600')

    @destructiveTest
    def test_get_zonecode(self):
        '''
        Test timezone.get_zonecode
        '''
        self.assertTrue(self.run_function('timezone.set_zone',
                                          ['Pacific/Wake']))
        self.assertEqual(self.run_function('timezone.get_zonecode'), 'WAKT')
        self.assertTrue(self.run_function('timezone.set_zone',
                                          ['America/Denver']))
        self.assertEqual(self.run_function('timezone.get_zonecode'), 'MDT')

    def test_list_zones(self):
        '''
        Test timezone.list_zones
        '''
        ret = self.run_function('timezone.list_zones')
        self.assertIn('America/Denver', ret)
        self.assertIn('Asia/Hong_Kong', ret)
        self.assertIn('Australia/Sydney', ret)
        self.assertIn('Europe/London', ret)

    def test_zone_compare(self):
        '''
        Test timezone.zone_compare
        '''
        self.assertTrue(self.run_function('timezone.set_zone',
                                          ['Pacific/Wake']))
        self.assertTrue(self.run_function('timezone.zone_compare',
                                          ['Pacific/Wake']))
        self.assertFalse(self.run_function('timezone.zone_compare',
                                           ['America/Denver']))

    @destructiveTest
    def test_get_set_using_network_time(self):
        '''
        Test timezone.get_using_network_time
        Test timezone.set_using_network_time
        '''
        self.assertTrue(self.run_function('timezone.set_using_network_time',
                                          [True]))
        self.assertTrue(self.run_function('timezone.get_using_network_time'))

        self.assertTrue(self.run_function('timezone.set_using_network_time',
                                          [False]))
        self.assertFalse(self.run_function('timezone.get_using_network_time'))

    @destructiveTest
    def test_get_set_time_server(self):
        '''
        Test timezone.get_time_server
        Test timezone.set_time_server
        '''
        self.assertTrue(self.run_function('timezone.set_time_server',
                                          ['time.spongebob.com']))
        self.assertEqual(self.run_function('timezone.get_time_server'),
                         'time.spongebob.com')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacTimezoneModuleTest)
