# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
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
from salt.modules import etcd_mod
from salt.utils import etcd_util

# Globals
etcd_mod.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EtcdModTestCase(TestCase):
    '''
    Test cases for salt.modules.etcd_mod
    '''
    # 'get_' function tests: 1

    def test_get(self):
        '''
        Test if it get a value from etcd, by direct path
        '''
        class MockEtcd(object):
            """
            Mock of etcd
            """
            value = 'salt'

            def __init__(self):
                self.key = None

            def get(self, key):
                """
                Mock of get method
                """
                self.key = key
                if key == '':
                    raise KeyError
                elif key == 'err':
                    raise ValueError
                return MockEtcd

        with patch.object(etcd_util, 'get_conn',
                          MagicMock(return_value=MockEtcd())):
            self.assertEqual(etcd_mod.get_('salt'), 'salt')

            with patch.object(etcd_util, 'tree', MagicMock(return_value={})):
                self.assertDictEqual(etcd_mod.get_('salt', recurse=True), {})

            self.assertEqual(etcd_mod.get_(''), '')

            self.assertRaises(ValueError, etcd_mod.get_, 'err')

    # 'set_' function tests: 1

    def test_set(self):
        '''
        Test if it set a value in etcd, by direct path
        '''
        class MockEtcd(object):
            """
            Mock of etcd
            """
            value = 'salt'

            def __init__(self):
                self.key = None
                self.value = None

            def write(self, key, value):
                """
                Mock of write method
                """
                self.key = key
                self.value = value
                if key == '':
                    raise KeyError
                elif key == 'err':
                    raise ValueError
                return MockEtcd

        with patch.object(etcd_util, 'get_conn',
                          MagicMock(return_value=MockEtcd())):
            self.assertEqual(etcd_mod.set_('salt', 'stack'), 'salt')

            self.assertEqual(etcd_mod.set_('', 'stack'), '')

            self.assertRaises(ValueError, etcd_mod.set_, 'err', 'stack')

    # 'ls_' function tests: 1

    def test_ls(self):
        '''
        Test if it return all keys and dirs inside a specific path
        '''
        class MockEtcd(object):
            """
            Mock of etcd
            """
            children = []

            def __init__(self):
                self.path = None

            def get(self, path):
                """
                Mock of get method
                """
                self.path = path
                if path == '':
                    raise KeyError
                elif path == 'err':
                    raise ValueError
                return MockEtcd

        with patch.object(etcd_util, 'get_conn',
                          MagicMock(return_value=MockEtcd())):
            self.assertDictEqual(etcd_mod.ls_(), {'/': {}})

            self.assertDictEqual(etcd_mod.ls_(''), {})

            self.assertRaises(ValueError, etcd_mod.ls_, 'err')

    # 'rm_' function tests: 1

    def test_rm(self):
        '''
        Test if it delete a key from etcd
        '''
        class MockEtcd(object):
            """
            Mock of etcd
            """
            children = []

            def __init__(self):
                self.key = None
                self.recursive = None

            def delete(self, key, recursive):
                """
                Mock of delete method
                """
                self.key = key
                self.recursive = recursive
                if key == '':
                    raise KeyError
                elif key == 'err':
                    raise ValueError
                if recursive:
                    return True
                else:
                    return False
                return MockEtcd

        with patch.object(etcd_util, 'get_conn',
                          MagicMock(return_value=MockEtcd())):
            self.assertFalse(etcd_mod.rm_('salt'))

            self.assertTrue(etcd_mod.rm_('salt', recurse=True))

            self.assertFalse(etcd_mod.rm_(''))

            self.assertRaises(ValueError, etcd_mod.rm_, 'err')

    # 'tree' function tests: 1

    def test_tree(self):
        '''
        Test if it recurse through etcd and return all values
        '''
        class MockEtcd(object):
            """
            Mock of etcd
            """
            children = []

        with patch.object(etcd_util, 'get_conn',
                          MagicMock(return_value=MockEtcd())):
            with patch.object(etcd_util, 'tree', MagicMock(return_value={})):
                self.assertDictEqual(etcd_mod.tree(), {})

            with patch.object(etcd_util, 'tree',
                              MagicMock(side_effect=KeyError)):
                self.assertDictEqual(etcd_mod.tree(), {})

            with patch.object(etcd_util, 'tree',
                              MagicMock(side_effect=Exception)):
                self.assertRaises(Exception, etcd_mod.tree)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(EtcdModTestCase, needs_daemon=False)
