# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt Libs
import salt.modules.s3 as s3


@skipIf(NO_MOCK, NO_MOCK_REASON)
class S3TestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        return {s3: {'__utils__': {'s3.query': MagicMock(return_value='A')}}}

    def test__get_key_defaults(self):
        mock = MagicMock(return_value='')
        with patch.dict(s3.__salt__, {'config.option': mock}):
            key, keyid, service_url, verify_ssl, kms_keyid, location, role_arn, path_style, https_enable = (
                s3._get_key(None, None, None, None, None, None, None, None, None))
            self.assertEqual(None, role_arn)
            self.assertEqual(None, key)
            self.assertEqual(None, keyid)
            self.assertEqual('s3.amazonaws.com', service_url)
            self.assertEqual('', verify_ssl)
            self.assertEqual('', location)
            self.assertEqual('', path_style)
            self.assertEqual('', https_enable)

    def test_delete(self):
        '''
        Test for delete a bucket, or delete an object from a bucket.
        '''
        with patch.object(s3, '_get_key',
                          return_value=('key', 'keyid', 'service_url',
                                        'verify_ssl', 'kms_keyid', 'location',
                                        'role_arn', 'path_style', 'https_enable')):
            self.assertEqual(s3.delete('bucket'), 'A')

    def test_get(self):
        '''
        Test for list the contents of a bucket, or return an object from a
        bucket.
        '''
        with patch.object(s3, '_get_key',
                          return_value=('key', 'keyid', 'service_url',
                                        'verify_ssl', 'kms_keyid', 'location',
                                        'role_arn', 'path_style', 'https_enable')):
            self.assertEqual(s3.get(), 'A')

    def test_head(self):
        '''
        Test for return the metadata for a bucket, or an object in a bucket.
        '''
        with patch.object(s3, '_get_key',
                          return_value=('key', 'keyid', 'service_url',
                                        'verify_ssl', 'kms_keyid', 'location',
                                        'role_arn', 'path_style', 'https_enable')):
            self.assertEqual(s3.head('bucket'), 'A')

    def test_put(self):
        '''
        Test for create a new bucket, or upload an object to a bucket.
        '''
        with patch.object(s3, '_get_key',
                          return_value=('key', 'keyid', 'service_url',
                                        'verify_ssl', 'kms_keyid', 'location',
                                        'role_arn', 'path_style', 'https_enable')):
            self.assertEqual(s3.put('bucket'), 'A')
