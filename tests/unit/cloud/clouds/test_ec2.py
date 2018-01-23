# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
from salt.cloud.clouds import ec2
from salt.exceptions import SaltCloudSystemExit

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, PropertyMock


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EC2TestCase(TestCase):
    '''
    Unit TestCase for salt.cloud.clouds.ec2 module.
    '''

    def test__validate_key_path_and_mode(self):

        # Key file exists
        with patch('os.path.exists', return_value=True):
            with patch('os.stat') as patched_stat:

                type(patched_stat.return_value).st_mode = PropertyMock(return_value=0o644)
                self.assertRaises(
                    SaltCloudSystemExit, ec2._validate_key_path_and_mode, 'key_file')

                type(patched_stat.return_value).st_mode = PropertyMock(return_value=0o600)
                self.assertTrue(ec2._validate_key_path_and_mode('key_file'))

                type(patched_stat.return_value).st_mode = PropertyMock(return_value=0o400)
                self.assertTrue(ec2._validate_key_path_and_mode('key_file'))

        # Key file does not exist
        with patch('os.path.exists', return_value=False):
            self.assertRaises(
                SaltCloudSystemExit, ec2._validate_key_path_and_mode, 'key_file')
