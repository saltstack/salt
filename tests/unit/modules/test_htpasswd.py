# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

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
import salt.modules.htpasswd as htpasswd


@skipIf(NO_MOCK, NO_MOCK_REASON)
class HtpasswdTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.htpasswd
    '''
    def setup_loader_modules(self):
        return {htpasswd: {}}

    # 'useradd' function tests: 1

    def test_useradd(self):
        '''
        Test if it adds an HTTP user using the htpasswd command
        '''
        mock = MagicMock(return_value={'out': 'Salt'})
        with patch.dict(htpasswd.__salt__, {'cmd.run_all': mock}), \
                patch('os.path.exists', MagicMock(return_value=True)):
            self.assertDictEqual(htpasswd.useradd('/etc/httpd/htpasswd',
                                                  'larry', 'badpassword'),
                                 {'out': 'Salt'})

    # 'userdel' function tests: 2

    def test_userdel(self):
        '''
        Test if it delete an HTTP user from the specified htpasswd file.
        '''
        mock = MagicMock(return_value='Salt')
        with patch.dict(htpasswd.__salt__, {'cmd.run': mock}), \
                patch('os.path.exists', MagicMock(return_value=True)):
            self.assertEqual(htpasswd.userdel('/etc/httpd/htpasswd',
                                              'larry'), ['Salt'])

    def test_userdel_missing_htpasswd(self):
        '''
        Test if it returns error when no htpasswd file exists
        '''
        with patch('os.path.exists', MagicMock(return_value=False)):
            self.assertEqual(htpasswd.userdel('/etc/httpd/htpasswd', 'larry'),
                             'Error: The specified htpasswd file does not exist')
