# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexander Pyatkin <asp@thexyz.net>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.states import htpasswd


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HtpasswdTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.htpasswd
    '''
    loader_module = htpasswd
    loader_module_globals = {'__opts__': {'test': False}}

    def test_user_exists_already(self):
        '''
        Test if it returns True when user already exists in htpasswd file
        '''

        mock = MagicMock(return_value={'retcode': 0})

        with patch.dict(htpasswd.__salt__, {'file.grep': mock}):
            ret = htpasswd.user_exists('larry', 'badpass',
                                       '/etc/httpd/htpasswd')
            expected = {'name': 'larry',
                        'result': True,
                        'comment': 'User already known',
                        'changes': {}}
            self.assertEqual(ret, expected)

    def test_new_user_success(self):
        '''
        Test if it returns True when new user is added to htpasswd file
        '''

        mock_grep = MagicMock(return_value={'retcode': 1})
        mock_useradd = MagicMock(return_value={'retcode': 0,
                                               'stderr': 'Success'})

        with patch.dict(htpasswd.__salt__,
                        {'file.grep': mock_grep,
                         'webutil.useradd': mock_useradd}):
            ret = htpasswd.user_exists('larry', 'badpass',
                                       '/etc/httpd/htpasswd')
            expected = {'name': 'larry',
                        'result': True,
                        'comment': 'Success',
                        'changes': {'larry': True}}
            self.assertEqual(ret, expected)

    def test_new_user_error(self):
        '''
        Test if it returns False when adding user to htpasswd failed
        '''

        mock_grep = MagicMock(return_value={'retcode': 1})
        mock_useradd = MagicMock(return_value={'retcode': 1,
                                               'stderr': 'Error'})

        with patch.dict(htpasswd.__salt__,
                        {'file.grep': mock_grep,
                         'webutil.useradd': mock_useradd}):
            ret = htpasswd.user_exists('larry', 'badpass',
                                       '/etc/httpd/htpasswd')
            expected = {'name': 'larry',
                        'result': False,
                        'comment': 'Error',
                        'changes': {}}
            self.assertEqual(ret, expected)
