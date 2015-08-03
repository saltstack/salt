# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
import salt.utils.s3
from salt.modules import s3


@skipIf(NO_MOCK, NO_MOCK_REASON)
class S3TestCase(TestCase):
    '''
    Test cases for salt.modules.s3
    '''
    def test_delete(self):
        '''
        Test for delete a bucket, or delete an object from a bucket.
        '''
        with patch.object(s3, '_get_key',
                          return_value=('key', 'keyid', 'service_url',
                                        'verify_ssl', 'location')):
            with patch.object(salt.utils.s3, 'query', return_value='A'):
                self.assertEqual(s3.delete('bucket'), 'A')

    def test_get(self):
        '''
        Test for list the contents of a bucket, or return an object from a
        bucket.
        '''
        with patch.object(s3, '_get_key',
                          return_value=('key', 'keyid', 'service_url',
                                        'verify_ssl', 'location')):
            with patch.object(salt.utils.s3, 'query', return_value='A'):
                self.assertEqual(s3.get(), 'A')

    def test_head(self):
        '''
        Test for return the metadata for a bucket, or an object in a bucket.
        '''
        with patch.object(s3, '_get_key',
                          return_value=('key', 'keyid', 'service_url',
                                        'verify_ssl', 'location')):
            with patch.object(salt.utils.s3, 'query', return_value='A'):
                self.assertEqual(s3.head('bucket'), 'A')

    def test_put(self):
        '''
        Test for create a new bucket, or upload an object to a bucket.
        '''
        with patch.object(s3, '_get_key',
                          return_value=('key', 'keyid', 'service_url',
                                        'verify_ssl', 'location')):
            with patch.object(salt.utils.s3, 'query', return_value='A'):
                self.assertEqual(s3.put('bucket'), 'A')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(S3TestCase, needs_daemon=False)
