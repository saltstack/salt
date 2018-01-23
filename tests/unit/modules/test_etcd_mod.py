# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    create_autospec,
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.etcd_mod as etcd_mod
import salt.utils.etcd_util as etcd_util


@skipIf(NO_MOCK, NO_MOCK_REASON)
class EtcdModTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.etcd_mod
    '''

    def setup_loader_modules(self):
        return {etcd_mod: {}}

    def setUp(self):
        self.instance = create_autospec(etcd_util.EtcdClient)
        self.EtcdClientMock = MagicMock()
        self.EtcdClientMock.return_value = self.instance

    def tearDown(self):
        del self.instance
        del self.EtcdClientMock

    # 'get_' function tests: 1

    def test_get(self):
        '''
        Test if it get a value from etcd, by direct path
        '''
        with patch.dict(etcd_mod.__utils__, {'etcd_util.get_conn': self.EtcdClientMock}):
            self.instance.get.return_value = 'stack'
            self.assertEqual(etcd_mod.get_('salt'), 'stack')
            self.instance.get.assert_called_with('salt', recurse=False)

            self.instance.tree.return_value = {}
            self.assertEqual(etcd_mod.get_('salt', recurse=True), {})
            self.instance.tree.assert_called_with('salt')

            self.instance.get.side_effect = Exception
            self.assertRaises(Exception, etcd_mod.get_, 'err')

    # 'set_' function tests: 1

    def test_set(self):
        '''
        Test if it set a key in etcd, by direct path
        '''
        with patch.dict(etcd_mod.__utils__, {'etcd_util.get_conn': self.EtcdClientMock}):
            self.instance.set.return_value = 'stack'
            self.assertEqual(etcd_mod.set_('salt', 'stack'), 'stack')
            self.instance.set.assert_called_with('salt', 'stack', directory=False, ttl=None)

            self.instance.set.return_value = True
            self.assertEqual(etcd_mod.set_('salt', '', directory=True), True)
            self.instance.set.assert_called_with('salt', '', directory=True, ttl=None)

            self.assertEqual(etcd_mod.set_('salt', '', directory=True, ttl=5), True)
            self.instance.set.assert_called_with('salt', '', directory=True, ttl=5)

            self.assertEqual(etcd_mod.set_('salt', '', None, 10, True), True)
            self.instance.set.assert_called_with('salt', '', directory=True, ttl=10)

            self.instance.set.side_effect = Exception
            self.assertRaises(Exception, etcd_mod.set_, 'err', 'stack')

    # 'update' function tests: 1

    def test_update(self):
        '''
        Test if can set multiple keys in etcd
        '''
        with patch.dict(etcd_mod.__utils__, {'etcd_util.get_conn': self.EtcdClientMock}):
            args = {
                'x': {
                    'y': {
                        'a': '1',
                        'b': '2',
                    }
                },
                'z': '4',
                'd': {},
            }

            result = {
                '/some/path/x/y/a': '1',
                '/some/path/x/y/b': '2',
                '/some/path/z': '4',
                '/some/path/d': {},
            }
            self.instance.update.return_value = result
            self.assertDictEqual(etcd_mod.update(args, path='/some/path'), result)
            self.instance.update.assert_called_with(args, '/some/path')
            self.assertDictEqual(etcd_mod.update(args), result)
            self.instance.update.assert_called_with(args, '')

    # 'ls_' function tests: 1

    def test_ls(self):
        '''
        Test if it return all keys and dirs inside a specific path
        '''
        with patch.dict(etcd_mod.__utils__, {'etcd_util.get_conn': self.EtcdClientMock}):
            self.instance.ls.return_value = {'/some-dir': {}}
            self.assertDictEqual(etcd_mod.ls_('/some-dir'), {'/some-dir': {}})
            self.instance.ls.assert_called_with('/some-dir')

            self.instance.ls.return_value = {'/': {}}
            self.assertDictEqual(etcd_mod.ls_(), {'/': {}})
            self.instance.ls.assert_called_with('/')

            self.instance.ls.side_effect = Exception
            self.assertRaises(Exception, etcd_mod.ls_, 'err')

    # 'rm_' function tests: 1

    def test_rm(self):
        '''
        Test if it delete a key from etcd
        '''
        with patch.dict(etcd_mod.__utils__, {'etcd_util.get_conn': self.EtcdClientMock}):
            self.instance.rm.return_value = False
            self.assertFalse(etcd_mod.rm_('dir'))
            self.instance.rm.assert_called_with('dir', recurse=False)

            self.instance.rm.return_value = True
            self.assertTrue(etcd_mod.rm_('dir', recurse=True))
            self.instance.rm.assert_called_with('dir', recurse=True)

            self.instance.rm.side_effect = Exception
            self.assertRaises(Exception, etcd_mod.rm_, 'err')

    # 'tree' function tests: 1

    def test_tree(self):
        '''
        Test if it recurses through etcd and return all values
        '''
        with patch.dict(etcd_mod.__utils__, {'etcd_util.get_conn': self.EtcdClientMock}):
            self.instance.tree.return_value = {}
            self.assertDictEqual(etcd_mod.tree('/some-dir'), {})
            self.instance.tree.assert_called_with('/some-dir')

            self.assertDictEqual(etcd_mod.tree(), {})
            self.instance.tree.assert_called_with('/')

            self.instance.tree.side_effect = Exception
            self.assertRaises(Exception, etcd_mod.tree, 'err')

    # 'watch' function tests: 1

    def test_watch(self):
        '''
        Test if watch returns the right tuples
        '''
        with patch.dict(etcd_mod.__utils__, {'etcd_util.get_conn': self.EtcdClientMock}):
            self.instance.watch.return_value = {
                'value': 'stack',
                'changed': True,
                'dir': False,
                'mIndex': 1,
                'key': '/salt'
            }
            self.assertEqual(etcd_mod.watch('/salt'), self.instance.watch.return_value)
            self.instance.watch.assert_called_with('/salt', recurse=False, timeout=0, index=None)

            self.instance.watch.return_value['dir'] = True
            self.assertEqual(etcd_mod.watch('/some-dir', recurse=True, timeout=5, index=10),
                             self.instance.watch.return_value)
            self.instance.watch.assert_called_with('/some-dir', recurse=True, timeout=5, index=10)

            self.assertEqual(etcd_mod.watch('/some-dir', True, None, 5, 10),
                             self.instance.watch.return_value)
            self.instance.watch.assert_called_with('/some-dir', recurse=True, timeout=5, index=10)
