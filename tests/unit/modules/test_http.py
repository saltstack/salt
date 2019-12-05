# -*- coding: utf-8 -*-
'''
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import tempfile

# Import Salt Testing Libs
from salt.ext import six
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch
from tests.support.helpers import destructiveTest

# Import Salt Libs
import salt.modules.http as http
import salt.utils.http


@skipIf(NO_MOCK, NO_MOCK_REASON)
@destructiveTest
class HttpTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.http
    '''

    def setUp(self):
        if six.PY3:
            self.dir_exist = tempfile.TemporaryDirectory().name
        else:
            self.dir_exist = tempfile.tempdir
        if not os.path.exists(self.dir_exist):
            os.mkdir(self.dir_exist)
        self.file_absent = os.path.join(self.dir_exist, 'file_absent.txt')

    def tearDown(self):
        if os.path.exists(self.file_absent):
            os.remove(self.file_absent)
        if os.path.exists(self.dir_exist):
            os.rmdir(self.dir_exist)

        del self.dir_exist
        del self.file_absent

    def setup_loader_modules(self):
        return {http: {}}

    def test_query(self):
        '''
        Test for Query a resource, and decode the return data
        '''
        with patch.object(salt.utils.http, 'query', return_value='A'):
            self.assertEqual(http.query('url'), 'A')

    def test_download_hash_is_valid(self):
        mock_file_modules = {'file.write': MagicMock(return_value=True),
                             'file.remove': MagicMock(return_value=True),
                             'file.rename': MagicMock(return_value=True)}
        with patch.dict(http.__salt__, mock_file_modules):
            with patch('urllib.request') as mock_request:
                mock_request.return_value.content = "Fake content"
                with patch.object(salt.utils.hashutils, 'get_hash', return_value='123456'):
                    ret_wanted = {'Changes': self.file_absent,
                                  'Success': '{} is present.'.format(self.file_absent)}
                    ret = http.download(self.file_absent,
                                        'http://fake/url/file.tar.gz',
                                        '123456')
                    self.assertEqual(ret, ret_wanted)

    def test_download_hash_is_not_valid(self):
        mock_file_modules = {'file.write': MagicMock(return_value=True),
                             'file.remove': MagicMock(return_value=True),
                             'file.rename': MagicMock(return_value=True)}
        with patch.dict(http.__salt__, mock_file_modules):
            with patch('urllib.request') as mock_request:
                mock_request.return_value.content = "Fake content"
                with patch.object(salt.utils.hashutils, 'get_hash', return_value='123456'):
                    ret_wanted = {'Error': {
                        'Hash not equals': {
                            'present': '123456',
                            'wanted': '654321'
                        }
                    }
                    }
                    ret = http.download(self.file_absent,
                                        'http://fake/url/file.tar.gz',
                                        '654321')
                    self.assertEqual(ret, ret_wanted)

    def test_download_is_already_present(self):
        mock_file_modules = {'file.write': MagicMock(return_value=True),
                             'file.remove': MagicMock(return_value=True),
                             'file.rename': MagicMock(return_value=True)}
        with patch.dict(http.__salt__, mock_file_modules):
            with patch('urllib.request') as mock_request:
                mock_request.return_value.content = "Fake content"
                with patch.object(salt.utils.hashutils, 'get_hash', return_value='123456'):
                    with patch.object(salt.utils.path, 'is_file', return_value=True):
                        ret_wanted = {'Success': '{} is already present.'.format(self.file_absent)}
                        ret = http.download(self.file_absent,
                                            'http://fake/url/file.tar.gz')
                        self.assertEqual(ret, ret_wanted)
