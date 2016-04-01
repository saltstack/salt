# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import sdb

# Globals
sdb.__opts__ = {}


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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SdbTestCase, needs_daemon=False)
