# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.utils.etcd_util as etcd_util
try:
    from urllib3.exceptions import ReadTimeoutError, MaxRetryError
    HAS_URLLIB3 = True
except ImportError:
    HAS_URLLIB3 = False

try:
    import etcd
    HAS_ETCD = True
except ImportError:
    HAS_ETCD = False


@skipIf(HAS_URLLIB3 is False, 'urllib3 module must be installed.')
@skipIf(HAS_ETCD is False, 'python-etcd module must be installed.')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class EtcdUtilTestCase(TestCase):
    '''
    Test cases for salt.utils.etcd_util
    '''
    # 'get_' function tests: 1

    def test_read(self):
        '''
        Test to make sure we interact with etcd correctly
        '''
        with patch('etcd.Client', autospec=True) as mock:
            etcd_client = mock.return_value
            etcd_return = MagicMock(value='salt')
            etcd_client.read.return_value = etcd_return
            client = etcd_util.EtcdClient({})

            self.assertEqual(client.read('/salt'), etcd_return)
            etcd_client.read.assert_called_with('/salt', recursive=False, wait=False, timeout=None)

            client.read('salt', True, True, 10, 5)
            etcd_client.read.assert_called_with('salt', recursive=True, wait=True, timeout=10, waitIndex=5)

            etcd_client.read.side_effect = etcd.EtcdKeyNotFound
            self.assertRaises(etcd.EtcdKeyNotFound, client.read, 'salt')

            etcd_client.read.side_effect = etcd.EtcdConnectionFailed
            self.assertRaises(etcd.EtcdConnectionFailed, client.read, 'salt')

            etcd_client.read.side_effect = etcd.EtcdValueError
            self.assertRaises(etcd.EtcdValueError, client.read, 'salt')

            etcd_client.read.side_effect = ValueError
            self.assertRaises(ValueError, client.read, 'salt')

            etcd_client.read.side_effect = ReadTimeoutError(None, None, None)
            self.assertRaises(etcd.EtcdConnectionFailed, client.read, 'salt')

            etcd_client.read.side_effect = MaxRetryError(None, None)
            self.assertRaises(etcd.EtcdConnectionFailed, client.read, 'salt')

    def test_get(self):
        '''
        Test if it get a value from etcd, by direct path
        '''
        with patch('etcd.Client') as mock:
            client = etcd_util.EtcdClient({})

            with patch.object(client, 'read', autospec=True) as mock:
                mock.return_value = MagicMock(value='stack')
                self.assertEqual(client.get('salt'), 'stack')
                mock.assert_called_with('salt', recursive=False)

                self.assertEqual(client.get('salt', recurse=True), 'stack')
                mock.assert_called_with('salt', recursive=True)

                # iter(list(Exception)) works correctly with both mock<1.1 and mock>=1.1
                mock.side_effect = iter([etcd.EtcdKeyNotFound()])
                self.assertEqual(client.get('not-found'), None)

                mock.side_effect = iter([etcd.EtcdConnectionFailed()])
                self.assertEqual(client.get('watching'), None)

                # python 2.6 test
                mock.side_effect = ValueError
                self.assertEqual(client.get('not-found'), None)

                mock.side_effect = Exception
                self.assertRaises(Exception, client.get, 'some-error')

    def test_tree(self):
        '''
        Test recursive gets
        '''
        with patch('etcd.Client') as mock:
            client = etcd_util.EtcdClient({})

            with patch.object(client, 'read', autospec=True) as mock:

                c1, c2 = MagicMock(), MagicMock()
                c1.__iter__.return_value = [
                    MagicMock(key='/x/a', value='1'),
                    MagicMock(key='/x/b', value='2'),
                    MagicMock(key='/x/c', dir=True)]
                c2.__iter__.return_value = [
                    MagicMock(key='/x/c/d', value='3')
                ]
                mock.side_effect = iter([
                    MagicMock(children=c1),
                    MagicMock(children=c2)
                ])
                self.assertDictEqual(client.tree('/x'), {'a': '1', 'b': '2', 'c': {'d': '3'}})
                mock.assert_any_call('/x')
                mock.assert_any_call('/x/c')

                # iter(list(Exception)) works correctly with both mock<1.1 and mock>=1.1
                mock.side_effect = iter([etcd.EtcdKeyNotFound()])
                self.assertEqual(client.tree('not-found'), None)

                mock.side_effect = ValueError
                self.assertEqual(client.tree('/x'), None)

                mock.side_effect = Exception
                self.assertRaises(Exception, client.tree, 'some-error')

    def test_ls(self):
        with patch('etcd.Client') as mock:
            client = etcd_util.EtcdClient({})

            with patch.object(client, 'read', autospec=True) as mock:
                c1 = MagicMock()
                c1.__iter__.return_value = [
                    MagicMock(key='/x/a', value='1'),
                    MagicMock(key='/x/b', value='2'),
                    MagicMock(key='/x/c', dir=True)]
                mock.return_value = MagicMock(children=c1)
                self.assertEqual(client.ls('/x'), {'/x': {'/x/a': '1', '/x/b': '2', '/x/c/': {}}})
                mock.assert_called_with('/x')

                # iter(list(Exception)) works correctly with both mock<1.1 and mock>=1.1
                mock.side_effect = iter([etcd.EtcdKeyNotFound()])
                self.assertEqual(client.ls('/not-found'), {})

                mock.side_effect = Exception
                self.assertRaises(Exception, client.tree, 'some-error')

    def test_write(self):
        with patch('etcd.Client', autospec=True) as mock:
            client = etcd_util.EtcdClient({})
            etcd_client = mock.return_value

            etcd_client.write.return_value = MagicMock(value='salt')
            self.assertEqual(client.write('/some-key', 'salt'), 'salt')
            etcd_client.write.assert_called_with('/some-key', 'salt', ttl=None, dir=False)

            self.assertEqual(client.write('/some-key', 'salt', ttl=5), 'salt')
            etcd_client.write.assert_called_with('/some-key', 'salt', ttl=5, dir=False)

            etcd_client.write.return_value = MagicMock(dir=True)
            self.assertEqual(client.write('/some-dir', 'salt', ttl=0, directory=True), True)
            etcd_client.write.assert_called_with('/some-dir', None, ttl=0, dir=True)

            # Check when a file is attempted to be written to a read-only root
            etcd_client.write.side_effect = etcd.EtcdRootReadOnly()
            self.assertEqual(client.write('/', 'some-val', directory=False), None)

            # Check when a directory is attempted to be written to a read-only root
            etcd_client.write.side_effect = etcd.EtcdRootReadOnly()
            self.assertEqual(client.write('/', None, directory=True), None)

            # Check when a file is attempted to be written when unable to connect to the service
            etcd_client.write.side_effect = MaxRetryError(None, None)
            self.assertEqual(client.write('/some-key', 'some-val', directory=False), None)

            # Check when a directory is attempted to be written when unable to connect to the service
            etcd_client.write.side_effect = MaxRetryError(None, None)
            self.assertEqual(client.write('/some-dir', None, directory=True), None)

            # Check when a file is attempted to be written to a directory that already exists (name-collision)
            etcd_client.write.side_effect = etcd.EtcdNotFile()
            self.assertEqual(client.write('/some-dir', 'some-val', directory=False), None)

            # Check when a directory is attempted to be written to a file that already exists (name-collision)
            etcd_client.write.side_effect = etcd.EtcdNotDir()
            self.assertEqual(client.write('/some-key', None, directory=True), None)

            # Check when a directory is attempted to be written to a directory that already exists (update-ttl)
            etcd_client.write.side_effect = etcd.EtcdNotFile()
            self.assertEqual(client.write('/some-dir', None, directory=True), True)

            etcd_client.write.side_effect = ValueError
            self.assertEqual(client.write('/some-key', 'some-val'), None)

            etcd_client.write.side_effect = Exception
            self.assertRaises(Exception, client.set, 'some-key', 'some-val')

    def test_flatten(self):
        with patch('etcd.Client', autospec=True) as mock:
            client = etcd_util.EtcdClient({})
            some_data = {
                '/x/y/a': '1',
                'x': {
                    'y': {
                        'b': '2'
                    }
                },
                'm/j/': '3',
                'z': '4',
                'd': {},
            }

            result_path = {
                '/test/x/y/a': '1',
                '/test/x/y/b': '2',
                '/test/m/j': '3',
                '/test/z': '4',
                '/test/d': {},
            }

            result_nopath = {
                '/x/y/a': '1',
                '/x/y/b': '2',
                '/m/j': '3',
                '/z': '4',
                '/d': {},
            }

            result_root = {
                '/x/y/a': '1',
                '/x/y/b': '2',
                '/m/j': '3',
                '/z': '4',
                '/d': {},
            }

            self.assertEqual(client._flatten(some_data, path='/test'), result_path)
            self.assertEqual(client._flatten(some_data, path='/'), result_root)
            self.assertEqual(client._flatten(some_data), result_nopath)

    def test_update(self):
        with patch('etcd.Client', autospec=True) as mock:
            client = etcd_util.EtcdClient({})
            some_data = {
                '/x/y/a': '1',
                'x': {
                    'y': {
                        'b': '3'
                    }
                },
                'm/j/': '3',
                'z': '4',
                'd': {},
            }

            result = {
                '/test/x/y/a': '1',
                '/test/x/y/b': '2',
                '/test/m/j': '3',
                '/test/z': '4',
                '/test/d': True,
            }

            flatten_result = {
                '/test/x/y/a': '1',
                '/test/x/y/b': '2',
                '/test/m/j': '3',
                '/test/z': '4',
                '/test/d': {}
            }
            client._flatten = MagicMock(return_value=flatten_result)

            self.assertEqual(client.update('/some/key', path='/blah'), None)

            with patch.object(client, 'write', autospec=True) as write_mock:
                def write_return(key, val, ttl=None, directory=None):
                    return result.get(key, None)
                write_mock.side_effect = write_return
                self.assertDictEqual(client.update(some_data, path='/test'), result)
                client._flatten.assert_called_with(some_data, '/test')
                self.assertEqual(write_mock.call_count, 5)

    def test_rm(self):
        with patch('etcd.Client', autospec=True) as mock:
            etcd_client = mock.return_value
            client = etcd_util.EtcdClient({})

            etcd_client.delete.return_value = True
            self.assertEqual(client.rm('/some-key'), True)
            etcd_client.delete.assert_called_with('/some-key', recursive=False)
            self.assertEqual(client.rm('/some-dir', recurse=True), True)
            etcd_client.delete.assert_called_with('/some-dir', recursive=True)

            etcd_client.delete.side_effect = etcd.EtcdNotFile()
            self.assertEqual(client.rm('/some-dir'), None)

            etcd_client.delete.side_effect = etcd.EtcdDirNotEmpty()
            self.assertEqual(client.rm('/some-key'), None)

            etcd_client.delete.side_effect = etcd.EtcdRootReadOnly()
            self.assertEqual(client.rm('/'), None)

            etcd_client.delete.side_effect = ValueError
            self.assertEqual(client.rm('/some-dir'), None)

            etcd_client.delete.side_effect = Exception
            self.assertRaises(Exception, client.rm, 'some-dir')

    def test_watch(self):
        with patch('etcd.Client', autospec=True) as client_mock:
            client = etcd_util.EtcdClient({})

            with patch.object(client, 'read', autospec=True) as mock:
                mock.return_value = MagicMock(value='stack', key='/some-key', modifiedIndex=1, dir=False)
                self.assertDictEqual(client.watch('/some-key'),
                                     {'value': 'stack', 'key': '/some-key', 'mIndex': 1, 'changed': True, 'dir': False})
                mock.assert_called_with('/some-key', wait=True, recursive=False, timeout=0, waitIndex=None)

                mock.side_effect = iter([etcd_util.EtcdUtilWatchTimeout, mock.return_value])
                self.assertDictEqual(client.watch('/some-key'),
                                     {'value': 'stack', 'changed': False, 'mIndex': 1, 'key': '/some-key', 'dir': False})

                mock.side_effect = iter([etcd_util.EtcdUtilWatchTimeout, etcd.EtcdKeyNotFound])
                self.assertEqual(client.watch('/some-key'),
                                 {'value': None, 'changed': False, 'mIndex': 0, 'key': '/some-key', 'dir': False})

                mock.side_effect = iter([etcd_util.EtcdUtilWatchTimeout, ValueError])
                self.assertEqual(client.watch('/some-key'), {})

                mock.side_effect = None
                mock.return_value = MagicMock(value='stack', key='/some-key', modifiedIndex=1, dir=True)
                self.assertDictEqual(client.watch('/some-dir', recurse=True, timeout=5, index=10),
                                     {'value': 'stack', 'key': '/some-key', 'mIndex': 1, 'changed': True, 'dir': True})
                mock.assert_called_with('/some-dir', wait=True, recursive=True, timeout=5, waitIndex=10)

                # iter(list(Exception)) works correctly with both mock<1.1 and mock>=1.1
                mock.side_effect = iter([MaxRetryError(None, None)])
                self.assertEqual(client.watch('/some-key'), {})

                mock.side_effect = iter([etcd.EtcdConnectionFailed()])
                self.assertEqual(client.watch('/some-key'), {})

                mock.side_effect = None
                mock.return_value = None
                self.assertEqual(client.watch('/some-key'), {})
