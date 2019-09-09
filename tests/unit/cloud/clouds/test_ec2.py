# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import tempfile

# Import Salt Libs
from salt.cloud.clouds import ec2
from salt.exceptions import SaltCloudSystemExit
import salt.utils.files

# Import Salt Testing Libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, PropertyMock
from tests.unit.test_crypt import PRIVKEY_DATA

PASS_DATA = (
    b'qOjCKDlBdcNEbJ/J8eRl7sH+bYIIm4cvHHY86gh2NEUnufFlFo0gGVTZR05Fj0cw3n/w7gR'
    b'urNXz5JoeSIHVuNI3YTwzL9yEAaC0kuy8EbOlO2yx8yPGdfml9BRwOV7A6b8UFo9co4H7fz'
    b'DdScMKU2yzvRYvp6N6Q2cJGBmPsemnXWWusb+1vZVWxcRAQmG3ogF6Z5rZSYAYH0N4rqJgH'
    b'mQfzuyb+jrBvV/IOoV1EdO9jGSH9338aS47NjrmNEN/SpnS6eCWZUwwyHbPASuOvWiY4QH/'
    b'0YZC6EGccwiUmt0ZOxIynk+tEyVPTkiS0V8RcZK6YKqMWHpKmPtLBzfuoA=='
)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EC2TestCase(TestCase, LoaderModuleMockMixin):
    '''
    Unit TestCase for salt.cloud.clouds.ec2 module.
    '''

    def setUp(self):
        super(EC2TestCase, self).setUp()
        with tempfile.NamedTemporaryFile(dir=RUNTIME_VARS.TMP, suffix='.pem', delete=True) as fp:
            self.key_file = fp.name

    def tearDown(self):
        super(EC2TestCase, self).tearDown()
        if os.path.exists(self.key_file):
            os.remove(self.key_file)

    def setup_loader_modules(self):
        return {ec2: {'__opts__': {}}}

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

    @skipIf(not ec2.HAS_M2 and not ec2.HAS_PYCRYPTO, 'Needs crypto library')
    @patch('salt.cloud.clouds.ec2._get_node')
    @patch('salt.cloud.clouds.ec2.get_location')
    @patch('salt.cloud.clouds.ec2.get_provider')
    @patch('salt.utils.aws.query')
    def test_get_password_data(self, query, get_provider, get_location, _get_node):
        query.return_value = [
            {
            'passwordData': PASS_DATA
            }
        ]
        _get_node.return_value = {'instanceId': 'i-abcdef'}
        get_location.return_value = 'us-west2'
        get_provider.return_value = 'ec2'
        with salt.utils.files.fopen(self.key_file, 'w') as fp:
            fp.write(PRIVKEY_DATA)
        ret = ec2.get_password_data(
            name='i-abcddef', kwargs={'key_file': self.key_file}, call='action'
        )
        assert ret['passwordData'] == PASS_DATA
        assert ret['password'] == 'testp4ss!'

    @patch('salt.cloud.clouds.ec2.config.get_cloud_config_value')
    @patch('salt.cloud.clouds.ec2.get_location')
    @patch('salt.cloud.clouds.ec2.get_provider')
    @patch('salt.cloud.clouds.ec2.aws.query')
    def test_get_imageid(self, aws_query, get_provider, get_location, config):
        '''
        test querying imageid function
        '''
        vm = {}
        ami = 'ami-1234'
        config.return_value = 'test/*'
        get_location.return_value = 'us-west2'
        get_provider.return_value = 'ec2'
        aws_query.return_value = [{'imageId': ami}]

        # test image filter
        self.assertEqual(ec2.get_imageid(vm), ami)

        # test ami-image
        config.return_value = ami
        self.assertEqual(ec2.get_imageid(vm), ami)

        # we should have only ran aws.query once when testing the aws filter
        aws_query.assert_called_once()
