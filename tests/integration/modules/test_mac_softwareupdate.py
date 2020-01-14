# -*- coding: utf-8 -*-
'''
integration tests for mac_softwareupdate
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

import pytest

# Import Salt Testing libs
from tests.support.unit import skipIf
from tests.support.case import ModuleCase

# Import Salt libs
import salt.utils.path
import salt.utils.platform


@pytest.mark.skip_if_not_root
@skipIf(not salt.utils.platform.is_darwin(), 'Test only available on macOS')
@skipIf(not salt.utils.path.which('softwareupdate'), '\'softwareupdate\' binary not found in $PATH')
class MacSoftwareUpdateModuleTest(ModuleCase):
    '''
    Validate the mac_softwareupdate module
    '''
    IGNORED_LIST = []
    SCHEDULE = False
    CATALOG = ''

    def setUp(self):
        '''
        Get current settings
        '''
        self.IGNORED_LIST = self.run_function('softwareupdate.list_ignored')
        self.SCHEDULE = self.run_function('softwareupdate.schedule')
        self.CATALOG = self.run_function('softwareupdate.get_catalog')

        super(MacSoftwareUpdateModuleTest, self).setUp()

    def tearDown(self):
        '''
        Reset to original settings
        '''
        if self.IGNORED_LIST:
            for item in self.IGNORED_LIST:
                self.run_function('softwareupdate.ignore', [item])
        else:
            self.run_function('softwareupdate.reset_ignored')

        self.run_function('softwareupdate.schedule', [self.SCHEDULE])

        if self.CATALOG == 'Default':
            self.run_function('softwareupdate.reset_catalog')
        else:
            self.run_function('softwareupdate.set_catalog', [self.CATALOG])

        super(MacSoftwareUpdateModuleTest, self).tearDown()

    def test_list_available(self):
        '''
        Test softwareupdate.list_available
        '''
        # Can't predict what will be returned, so can only test that the return
        # is the correct type, dict
        assert isinstance(self.run_function('softwareupdate.list_available'), dict)

    @pytest.mark.destructive_test
    def test_ignore(self):
        '''
        Test softwareupdate.ignore
        Test softwareupdate.list_ignored
        Test softwareupdate.reset_ignored
        '''
        # Test reset_ignored
        assert self.run_function('softwareupdate.reset_ignored')
        assert self.run_function('softwareupdate.list_ignored') == []

        # Test ignore
        assert self.run_function('softwareupdate.ignore', ['spongebob'])
        assert self.run_function('softwareupdate.ignore', ['squidward'])

        # Test list_ignored and verify ignore
        assert 'spongebob' in \
            self.run_function('softwareupdate.list_ignored')
        assert 'squidward' in \
            self.run_function('softwareupdate.list_ignored')

    @pytest.mark.destructive_test
    def test_schedule(self):
        '''
        Test softwareupdate.schedule_enable
        Test softwareupdate.schedule_enabled
        '''
        # Test enable
        assert self.run_function('softwareupdate.schedule_enable', [True])
        assert self.run_function('softwareupdate.schedule_enabled')

        # Test disable in case it was already enabled
        assert self.run_function('softwareupdate.schedule_enable', [False])
        assert not self.run_function('softwareupdate.schedule_enabled')

    @pytest.mark.destructive_test
    def test_update(self):
        '''
        Test softwareupdate.update_all
        Test softwareupdate.update
        Test softwareupdate.update_available

        Need to know the names of updates that are available to properly test
        the update functions...
        '''
        # There's no way to know what the dictionary will contain, so all we can
        # check is that the return is a dictionary
        assert isinstance(self.run_function('softwareupdate.update_all'), dict)

        # Test update_available
        assert not self.run_function('softwareupdate.update_available', ['spongebob'])

        # Test update not available
        assert 'Update not available' in \
            self.run_function('softwareupdate.update', ['spongebob'])

    def test_list_downloads(self):
        '''
        Test softwareupdate.list_downloads
        '''
        assert isinstance(self.run_function('softwareupdate.list_downloads'), list)

    @pytest.mark.destructive_test
    def test_download(self):
        '''
        Test softwareupdate.download

        Need to know the names of updates that are available to properly test
        the download function
        '''
        # Test update not available
        assert 'Update not available' in \
            self.run_function('softwareupdate.download', ['spongebob'])

    @pytest.mark.destructive_test
    def test_download_all(self):
        '''
        Test softwareupdate.download_all
        '''
        assert isinstance(self.run_function('softwareupdate.download_all'), list)

    @pytest.mark.destructive_test
    def test_get_set_reset_catalog(self):
        '''
        Test softwareupdate.download_all
        '''
        # Reset the catalog
        assert self.run_function('softwareupdate.reset_catalog')
        assert self.run_function('softwareupdate.get_catalog') == \
                         'Default'

        # Test setting and getting the catalog
        assert self.run_function('softwareupdate.set_catalog', ['spongebob'])
        assert self.run_function('softwareupdate.get_catalog') == 'spongebob'

        # Test reset the catalog
        assert self.run_function('softwareupdate.reset_catalog')
        assert self.run_function('softwareupdate.get_catalog') == \
                         'Default'
