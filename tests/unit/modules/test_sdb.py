# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import sdb

# Globals
sdb.__opts__ = {}
sdb.__utils__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SdbTestCase(TestCase):
    '''
    Test cases for salt.modules.sdb
    '''
    # 'get' function tests: 1

    def test_get(self):
        '''
        Test if it gets a value from a db, using a uri in the form of
        sdb://<profile>/<key>
        '''
        self.assertEqual(sdb.get('sdb://salt/foo'), 'sdb://salt/foo')

    # 'set_' function tests: 1

    def test_set(self):
        '''
        Test if it sets a value from a db, using a uri in the form of
        sdb://<profile>/<key>
        '''
        self.assertFalse(sdb.set_('sdb://mymemcached/foo', 'bar'))
