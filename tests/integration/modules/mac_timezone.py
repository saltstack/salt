# -*- coding: utf-8 -*-
'''
Integration tests for mac_timezone

If using parallels, make sure Time sync is turned off. Otherwise, parallels will
keep changing your date/time settings while the tests are running. To turn off
Time sync do the following:
    - Go to actions -> configure
    - Select options at the top and 'More Options' on the left
    - Set time to 'Do not sync'
'''

# Import python libs
from __future__ import absolute_import
import datetime

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, destructiveTest
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils


class MacTimezoneModuleTest(integration.ModuleCase):
    '''
    Validate the mac_timezone module
    '''
    USE_NETWORK_TIME = False
    TIME_SERVER = 'time.apple.com'
    TIME_ZONE = ''
    CURRENT_DATE = ''
    CURRENT_TIME = ''

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

        self.USE_NETWORK_TIME = self.run_function('timezone.get_using_network_time')
        self.TIME_SERVER = self.run_function('timezone.get_time_server')
        self.TIME_ZONE = self.run_function('timezone.get_zone')
        self.CURRENT_DATE = self.run_function('timezone.get_date')
        self.CURRENT_TIME = self.run_function('timezone.get_time')

        self.run_function('timezone.set_using_network_time', [False])
        self.run_function('timezone.set_zone', ['America/Denver'])

    def tearDown(self):
        '''
        Reset to original settings
        '''
        self.run_function('timezone.set_time_server', [self.TIME_SERVER])
        self.run_function('timezone.set_using_network_time',
                          [self.USE_NETWORK_TIME])
        self.run_function('timezone.set_zone', [self.TIME_ZONE])
        if not self.USE_NETWORK_TIME:
            self.run_function('timezone.set_date', [self.CURRENT_DATE])
            self.run_function('timezone.set_time', [self.CURRENT_TIME])

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

    def test_get_time(self):
        '''
        Test timezone.get_time
        '''
        text_time = self.run_function('timezone.get_time')
        self.assertNotEqual(text_time, 'Invalid Timestamp')
        obj_date = datetime.datetime.strptime(text_time, '%H:%M:%S')
        self.assertIsInstance(obj_date, datetime.date)

    @destructiveTest
    def test_set_time(self):
        '''
        Test timezone.set_time
        '''
        # Correct Functionality
        self.assertTrue(self.run_function('timezone.set_time', ['3:14']))

        # Test bad time format
        self.assertEqual(
            self.run_function('timezone.set_time', ['3:71']),
            'ERROR executing \'timezone.set_time\': '
            'Invalid Date/Time Format: 3:71')

    @destructiveTest
    def test_get_set_zone(self):
        '''
        Test timezone.get_zone
        Test timezone.set_zone
        '''
        # Correct Functionality
        self.assertTrue(
            self.run_function('timezone.set_zone', ['Pacific/Wake']))
        self.assertEqual(
            self.run_function('timezone.get_zone'), 'Pacific/Wake')

        # Test bad time zone
        self.assertEqual(
            self.run_function('timezone.set_zone', ['spongebob']),
            'ERROR executing \'timezone.set_zone\': '
            'Invalid Timezone: spongebob')

    def test_get_offset(self):
        '''
        Test timezone.get_offset
        '''
        self.assertTrue(
            self.run_function('timezone.set_zone', ['Pacific/Wake']))
        self.assertIsInstance(self.run_function('timezone.get_offset'), str)
        self.assertEqual(self.run_function('timezone.get_offset'), '+1200')

        self.assertTrue(
            self.run_function('timezone.set_zone', ['America/Los_Angeles']))
        self.assertIsInstance(self.run_function('timezone.get_offset'), str)
        self.assertEqual(self.run_function('timezone.get_offset'), '-0700')

    @destructiveTest
    def test_get_set_zonecode(self):
        '''
        Test timezone.get_zonecode
        Test timezone.set_zonecode
        '''
        self.assertTrue(
            self.run_function('timezone.set_zone', ['America/Los_Angeles']))
        self.assertIsInstance(self.run_function('timezone.get_zonecode'), str)
        self.assertEqual(self.run_function('timezone.get_zonecode'), 'PDT')

        self.assertTrue(
            self.run_function('timezone.set_zone', ['Pacific/Wake']))
        self.assertIsInstance(self.run_function('timezone.get_zonecode'), str)
        self.assertEqual(self.run_function('timezone.get_zonecode'), 'WAKT')

    def test_list_zones(self):
        '''
        Test timezone.list_zones
        '''
        zones = self.run_function('timezone.list_zones')
        self.assertIsInstance(self.run_function('timezone.list_zones'), list)
        self.assertIn(
            'America/Denver',
            self.run_function('timezone.list_zones'))
        self.assertIn(
            'America/Los_Angeles',
            self.run_function('timezone.list_zones'))

    @destructiveTest
    def test_zone_compare(self):
        '''
        Test timezone.zone_compare
        '''
        self.assertTrue(
            self.run_function('timezone.set_zone', ['America/Denver']))
        self.assertTrue(
            self.run_function('timezone.zone_compare', ['America/Denver']))
        self.assertFalse(
            self.run_function('timezone.zone_compare', ['Pacific/Wake']))

    @destructiveTest
    def test_get_set_using_network_time(self):
        '''
        Test timezone.get_using_network_time
        Test timezone.set_using_network_time
        '''
        self.assertTrue(
            self.run_function('timezone.set_using_network_time', [True]))
        self.assertTrue(self.run_function('timezone.get_using_network_time'))

        self.assertTrue(
            self.run_function('timezone.set_using_network_time', [False]))
        self.assertFalse(self.run_function('timezone.get_using_network_time'))

    @destructiveTest
    def test_get_set_time_server(self):
        '''
        Test timezone.get_time_server
        Test timezone.set_time_server
        '''
        self.assertTrue(
            self.run_function('timezone.set_time_server', ['spongebob.com']))
        self.assertEqual(
            self.run_function('timezone.get_time_server'), 'spongebob.com')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacTimezoneModuleTest)
