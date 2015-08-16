# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import htpasswd

# Globals
htpasswd.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HtpasswdTestCase(TestCase):
    '''
    Test cases for salt.modules.htpasswd
    '''
    # 'useradd_all' function tests: 1

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_useradd_all(self):
        '''
        Test if it adds an HTTP user using the htpasswd command
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(htpasswd.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(htpasswd.useradd_all('/etc/httpd/htpasswd',
                                                 'larry', 'badpassword'))

    # 'useradd' function tests: 1

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_useradd(self):
        '''
        Test if it adds an HTTP user using the htpasswd command
        '''
        mock = MagicMock(return_value={'out': 'Salt'})
        with patch.dict(htpasswd.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(htpasswd.useradd('/etc/httpd/htpasswd',
                                                  'larry', 'badpassword'),
                                 {'out': 'Salt'})

    # 'userdel' function tests: 2

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_userdel(self):
        '''
        Test if it delete an HTTP user from the specified htpasswd file.
        '''
        mock = MagicMock(return_value='Salt')
        with patch.dict(htpasswd.__salt__, {'cmd.run': mock}):
            self.assertEqual(htpasswd.userdel('/etc/httpd/htpasswd',
                                              'larry'), ['Salt'])

    @patch('os.path.exists', MagicMock(return_value=False))
    def test_userdel_missing_htpasswd(self):
        '''
        Test if it returns error when no htpasswd file exists
        '''
        self.assertEqual(htpasswd.userdel('/etc/httpd/htpasswd', 'larry'),
                         'Error: The specified htpasswd file does not exist')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(HtpasswdTestCase, needs_daemon=False)
