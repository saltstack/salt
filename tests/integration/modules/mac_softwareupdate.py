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
        '''
        self.assertTrue(self.run_function('softwareupdate.reset_ignored'))
        self.assertTrue(
            self.run_function('softwareupdate.ignore', ['spongebob']),
            'spongebob')

    @destructiveTest
    def test_list_ignored(self):
        '''
        Test softwareupdate.list_ignored
        '''
        self.assertTrue(self.run_function('softwareupdate.reset_ignored'))
        self.assertIn(self.run_function('softwareupdate.ignore', ['spongebob']),
                      'spongebob')
        self.assertIn(self.run_function('softwareupdate.ignore', ['squidward']),
                      'squidward')
        ret = self.run_function('softwareupdate.list_ignored')
        self.assertIn('spongebob', ret)
        self.assertIn('squidward', ret)

    @destructiveTest
    def test_reset_ignored(self):
        '''
        Test softwareupdate.reset_ignored
        '''
        ret = self.run_function('softwareupdate.reset_ignored')
        self.assertTrue(isinstance(ret, dict) or ret is None)
        self.assertIsNone(self.run_function('softwareupdate.list_ignored'))

    @destructiveTest
    def test_schedule(self):
        '''
        Test softwareupdate.schedule
        '''
        self.assertTrue(self.run_function('softwareupdate.schedule', [True]))
        self.assertTrue(self.run_function('softwareupdate.schedule'))
        self.assertFalse(self.run_function('softwareupdate.schedule', [False]))
        self.assertFalse(self.run_function('softwareupdate.schedule'))

    @destructiveTest
    def test_upgrade(self):
        '''
        Test softwareupdate.upgrade
        '''
        ret = self.run_function('softwareupdate.upgrade')
        self.assertTrue(isinstance(ret, dict) or ret is None)

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
