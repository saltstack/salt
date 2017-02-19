# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import
import time

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
from salt.modules import ldapmod


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LdapmodTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.ldapmod
    '''
    loader_module = ldapmod

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
