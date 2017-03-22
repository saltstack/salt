# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import os
import tempfile

# Import Salt Libs
from salt.cloud.clouds import ec2
from salt.exceptions import SaltCloudSystemExit

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EC2TestCase(TestCase, LoaderModuleMockMixin):
    '''
    Unit TestCase for salt.cloud.clouds.ec2 module.
    '''

    def setup_loader_modules(self):
        return {ec2: {}}

    def test__validate_key_path_and_mode(self):
        with tempfile.NamedTemporaryFile() as f:
            key_file = f.name

            os.chmod(key_file, 0o644)
            self.assertRaises(SaltCloudSystemExit,
                              ec2._validate_key_path_and_mode,
                              key_file)
            os.chmod(key_file, 0o600)
            self.assertTrue(ec2._validate_key_path_and_mode(key_file))
            os.chmod(key_file, 0o400)
            self.assertTrue(ec2._validate_key_path_and_mode(key_file))

        # tmp file removed
        self.assertRaises(SaltCloudSystemExit,
                          ec2._validate_key_path_and_mode,
                          key_file)
