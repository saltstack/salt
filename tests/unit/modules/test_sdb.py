# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase

# Import Salt Libs
import salt.modules.sdb as sdb


class SdbTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.sdb
    '''
    def setup_loader_modules(self):
        return {sdb: {}}

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
