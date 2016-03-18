# -*- coding: utf-8 -*-
'''
integration tests for mac_softwareupdate
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, destructiveTest
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

IGNORED_LIST = []
SCHEDULE = False
CATALOG = ''


class MacSoftwareUpdateModuleTest(integration.ModuleCase):
    '''
    Validate the mac_softwareupdate module
    '''

    def setUp(self):
        '''
        Get current settings
        '''
        if not salt.utils.is_darwin():
            self.skipTest('Test only available on Mac OS X')

        if not salt.utils.which('softwareupdate'):
            self.skipTest('Test requires softwareupdate binary')

        if salt.utils.get_uid(salt.utils.get_user()) != 0:
            self.skipTest('Test requires root')

        IGNORED_LIST = self.run_function('softwareupdate.list_ignored')
        SCHEDULE = self.run_function('softwareupdate.schedule')
        CATALOG = self.run_function('softwareupdate.get_catalog')

        super(MacSoftwareUpdateModuleTest, self).setUp()

    def tearDown(self):
        '''
        Reset to original settings
        '''
        if IGNORED_LIST:
            for item in IGNORED_LIST:
                self.run_function('softwareupdate.ignore', [item])
        else:
            self.run_function('softwareupdate.reset_ignored')

        self.run_function('softwareupdate.schedule', [SCHEDULE])

        if CATALOG == 'Default':
            self.run_function('softwareupdate.reset_catalog')
        else:
            self.run_function('softwareupdate.set_catalog', [CATALOG])

        super(MacSoftwareUpdateModuleTest, self).tearDown()

    def test_list_available(self):
        '''
        Test softwareupdate.list_available
        '''
        # Can't predict what will be returned, so can only test that the return
        # is the correct type, dict
        self.assertIsInstance(
            self.run_function('softwareupdate.list_available'), dict)

    @destructiveTest
    def test_ignore(self):
        '''
        Test softwareupdate.ignore
        Test softwareupdate.list_ignored
        Test softwareupdate.reset_ignored
        '''
        # Test reset_ignored
        self.assertTrue(self.run_function('softwareupdate.reset_ignored'))
        self.assertEqual(self.run_function('softwareupdate.list_ignored'), [])

        # Test ignore
        self.assertTrue(
            self.run_function('softwareupdate.ignore', ['spongebob']))
        self.assertTrue(
            self.run_function('softwareupdate.ignore', ['squidward']))

        # Test list_ignored and verify ignore
        self.assertIn(
            'spongebob',
            self.run_function('softwareupdate.list_ignored'))
        self.assertIn(
            'squidward',
            self.run_function('softwareupdate.list_ignored'))

    @destructiveTest
    def test_schedule(self):
        '''
        Test softwareupdate.schedule_enable
        Test softwareupdate.schedule_enabled
        '''
        # Test enable
        self.assertTrue(
            self.run_function('softwareupdate.schedule_enable', [True]))
        self.assertTrue(self.run_function('softwareupdate.schedule_enabled'))

        # Test disable in case it was already enabled
        self.assertFalse(
            self.run_function('softwareupdate.schedule_enable', [False]))
        self.assertFalse(self.run_function('softwareupdate.schedule_enabled'))

    @destructiveTest
    def test_update(self):
        '''
        Test softwareupdate.update_all
        Test softwareupdate.update
        Test softwareupdate.update_available
        '''
        # There's no way to know what the dictionary will contain, so all we can
        # check is that the return is a dictionary
        self.assertIsInstance(
            self.run_function('softwareupdate.update_all'), dict)

        # Test update not available
        self.assertIn(
            'Update not available',
            self.run_function('softwareupdate.update', ['spongebob']))

    @destructiveTest
    def test_install(self):
        '''
        Test softwareupdate.install
        '''
        ret = self.run_function('softwareupdate.install', ['spongebob'])
        self.assertIsNone(ret['spongebob'])

    def test_upgrade_available(self):
        '''
        Test softwareupdate.upgrade_available
        '''
        ret = self.run_function('softwareupdate.upgrade_available',
                                ['spongebob'])
        self.assertTrue(isinstance(ret, dict) or ret is False)

    def test_list_downloads(self):
        '''
        Test softwareupdate.list_downloads
        '''
        ret = self.run_function('softwareupdate.list_downloads')
        self.assertTrue(isinstance(ret, list) or ret is None)

    @destructiveTest
    def test_download(self):
        '''
        Test softwareupdate.download
        '''
        ret = self.run_function('softwareupdate.download', ['spongebob'])
        self.assertTrue(isinstance(ret, list) or ret is None)

    @destructiveTest
    def test_download_all(self):
        '''
        Test softwareupdate.download_all
        '''
        ret = self.run_function('softwareupdate.download_all')
        self.assertTrue(isinstance(ret, list) or ret is None)

    @destructiveTest
    def test_get_set_reset_catalog(self):
        '''
        Test softwareupdate.download_all
        '''
        self.assertTrue(self.run_function('softwareupdate.reset_catalog'))
        self.assertEqual(self.run_function('softwareupdate.get_catalog'),
                         'Default')
        self.assertTrue(self.run_function('softwareupdate.set_catalog',
                                          ['spongebob']))
        self.assertEqual(self.run_function('softwareupdate.get_catalog'),
                         'spongebob')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MacSoftwareUpdateModuleTest)
