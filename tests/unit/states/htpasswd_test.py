# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexander Pyatkin <asp@thexyz.net>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import htpasswd

# Globals
htpasswd.__salt__ = {}
htpasswd.__opts__ = {'test': False}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HtpasswdTestCase(TestCase):
    '''
    Test cases for salt.states.htpasswd
    '''

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
                         'webutil.useradd_all': mock_useradd}):
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
                         'webutil.useradd_all': mock_useradd}):
            ret = htpasswd.user_exists('larry', 'badpass',
                                       '/etc/httpd/htpasswd')
            expected = {'name': 'larry',
                        'result': False,
                        'comment': 'Error',
                        'changes': {}}
            self.assertEqual(ret, expected)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(HtpasswdTestCase, needs_daemon=False)
