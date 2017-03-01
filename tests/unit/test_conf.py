# -*- coding: utf-8 -*-
'''
Unit tests for the files in the salt/conf directory.
'''

# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
)

# Import Salt libs
import salt.config

SAMPLE_CONF_DIR = os.path.dirname(os.path.realpath(__file__)).split('tests')[0] + 'conf/'


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ConfTest(TestCase):
    '''
    Validate files in the salt/conf directory.
    '''

    def test_conf_master_sample_is_commented(self):
        '''
        The sample config file located in salt/conf/master must be completely
        commented out. This test checks for any lines that are not commented or blank.
        '''
        master_config = SAMPLE_CONF_DIR + 'master'
        ret = salt.config._read_conf_file(master_config)
        self.assertEqual(
            ret,
            {},
            'Sample config file \'{0}\' must be commented out.'.format(
                master_config
            )
        )

    def test_conf_minion_sample_is_commented(self):
        '''
        The sample config file located in salt/conf/minion must be completely
        commented out. This test checks for any lines that are not commented or blank.
        '''
        minion_config = SAMPLE_CONF_DIR + 'minion'
        ret = salt.config._read_conf_file(minion_config)
        self.assertEqual(
            ret,
            {},
            'Sample config file \'{0}\' must be commented out.'.format(
                minion_config
            )
        )

    def test_conf_cloud_sample_is_commented(self):
        '''
        The sample config file located in salt/conf/cloud must be completely
        commented out. This test checks for any lines that are not commented or blank.
        '''
        cloud_config = SAMPLE_CONF_DIR + 'cloud'
        ret = salt.config._read_conf_file(cloud_config)
        self.assertEqual(
            ret,
            {},
            'Sample config file \'{0}\' must be commented out.'.format(
                cloud_config
            )
        )

    def test_conf_cloud_profiles_sample_is_commented(self):
        '''
        The sample config file located in salt/conf/cloud.profiles must be completely
        commented out. This test checks for any lines that are not commented or blank.
        '''
        cloud_profiles_config = SAMPLE_CONF_DIR + 'cloud.profiles'
        ret = salt.config._read_conf_file(cloud_profiles_config)
        self.assertEqual(
            ret,
            {},
            'Sample config file \'{0}\' must be commented out.'.format(
                cloud_profiles_config
            )
        )

    def test_conf_cloud_providers_sample_is_commented(self):
        '''
        The sample config file located in salt/conf/cloud.providers must be completely
        commented out. This test checks for any lines that are not commented or blank.
        '''
        cloud_providers_config = SAMPLE_CONF_DIR + 'cloud.providers'
        ret = salt.config._read_conf_file(cloud_providers_config)
        self.assertEqual(
            ret,
            {},
            'Sample config file \'{0}\' must be commented out.'.format(
                cloud_providers_config
            )
        )

    def test_conf_proxy_sample_is_commented(self):
        '''
        The sample config file located in salt/conf/proxy must be completely
        commented out. This test checks for any lines that are not commented or blank.
        '''
        proxy_config = SAMPLE_CONF_DIR + 'proxy'
        ret = salt.config._read_conf_file(proxy_config)
        self.assertEqual(
            ret,
            {},
            'Sample config file \'{0}\' must be commented out.'.format(
                proxy_config
            )
        )

    def test_conf_roster_sample_is_commented(self):
        '''
        The sample config file located in salt/conf/roster must be completely
        commented out. This test checks for any lines that are not commented or blank.
        '''
        roster_config = SAMPLE_CONF_DIR + 'roster'
        ret = salt.config._read_conf_file(roster_config)
        self.assertEqual(
            ret,
            {},
            'Sample config file \'{0}\' must be commented out.'.format(
                roster_config
            )
        )

    def test_conf_cloud_profiles_d_files_are_commented(self):
        '''
        All cloud profile sample configs in salt/conf/cloud.profiles.d/* must be completely
        commented out. This test loops through all of the files in that directory to check
        for any lines that are not commented or blank.
        '''
        cloud_sample_files = os.listdir(SAMPLE_CONF_DIR + 'cloud.profiles.d/')
        for conf_file in cloud_sample_files:
            profile_conf = SAMPLE_CONF_DIR + 'cloud.profiles.d/' + conf_file
            ret = salt.config._read_conf_file(profile_conf)
            self.assertEqual(
                ret,
                {},
                'Sample config file \'{0}\' must be commented out.'.format(
                    conf_file
                )
            )

    def test_conf_cloud_providers_d_files_are_commented(self):
        '''
        All cloud profile sample configs in salt/conf/cloud.providers.d/* must be completely
        commented out. This test loops through all of the files in that directory to check
        for any lines that are not commented or blank.
        '''
        cloud_sample_files = os.listdir(SAMPLE_CONF_DIR + 'cloud.providers.d/')
        for conf_file in cloud_sample_files:
            provider_conf = SAMPLE_CONF_DIR + 'cloud.providers.d/' + conf_file
            ret = salt.config._read_conf_file(provider_conf)
            self.assertEqual(
                ret,
                {},
                'Sample config file \'{0}\' must be commented out.'.format(
                    conf_file
                )
            )

    def test_conf_cloud_maps_d_files_are_commented(self):
        '''
        All cloud profile sample configs in salt/conf/cloud.maps.d/* must be completely
        commented out. This test loops through all of the files in that directory to check
        for any lines that are not commented or blank.
        '''
        cloud_sample_files = os.listdir(SAMPLE_CONF_DIR + 'cloud.maps.d/')
        for conf_file in cloud_sample_files:
            map_conf = SAMPLE_CONF_DIR + 'cloud.maps.d/' + conf_file
            ret = salt.config._read_conf_file(map_conf)
            self.assertEqual(
                ret,
                {},
                'Sample config file \'{0}\' must be commented out.'.format(
                    conf_file
                )
            )
