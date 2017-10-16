# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import
import time

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
from salt.modules import ldapmod

# Globals
ldapmod.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LdapmodTestCase(TestCase):
    '''
    Test cases for salt.modules.ldapmod
    '''
    # 'search' function tests: 1

    def test_search(self):
        '''
        Test if it run an arbitrary LDAP query and return the results.
        '''
        class MockConnect(object):
            '''
            Mocking _connect method
            '''
            def __init__(self):
                self.bdn = None
                self.scope = None
                self._filter = None
                self.attrs = None

            def search_s(self, bdn, scope, _filter, attrs):
                '''
                Mock function for search_s
                '''
                self.bdn = bdn
                self.scope = scope
                self._filter = _filter
                self.attrs = attrs
                return 'SALT'

        mock = MagicMock(return_value=True)
        with patch.dict(ldapmod.__salt__, {'config.option': mock}):
            with patch.object(ldapmod, '_connect',
                              MagicMock(return_value=MockConnect())):
                with patch.object(time, 'time', MagicMock(return_value=8e-04)):
                    self.assertDictEqual(ldapmod.search(filter='myhost'),
                                         {'count': 4, 'results': 'SALT',
                                          'time': {'raw': '0.0',
                                                   'human': '0.0ms'}})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LdapmodTestCase, needs_daemon=False)
