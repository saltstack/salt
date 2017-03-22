# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

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
import salt.modules.ipset as ipset


@skipIf(NO_MOCK, NO_MOCK_REASON)
class IpsetTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.aptpkg
    '''
    def setup_loader_modules(self):
        return {ipset: {}}

    def test_version(self):
        '''
        Test for Return version from ipset --version
        '''
        with patch.object(ipset, '_ipset_cmd', return_value='A'):
            mock = MagicMock(return_value="A\nB\nC")
            with patch.dict(ipset.__salt__, {'cmd.run': mock}):
                self.assertEqual(ipset.version(), 'B')

    def test_new_set(self):
        '''
        Test for Create new custom set
        '''
        self.assertEqual(ipset.new_set(), 'Error: Set needs to be specified')

        self.assertEqual(ipset.new_set('s'),
                         'Error: Set Type needs to be specified')

        self.assertEqual(ipset.new_set('s', 'd'), 'Error: Set Type is invalid')

        self.assertEqual(ipset.new_set('s', 'bitmap:ip'),
                         'Error: range is a required argument')

        mock = MagicMock(return_value=False)
        with patch.dict(ipset.__salt__, {'cmd.run': mock}):
            self.assertTrue(ipset.new_set('s', 'bitmap:ip', range='range'))

    def test_delete_set(self):
        '''
        Test for Delete ipset set.
        '''
        self.assertEqual(ipset.delete_set(),
                         'Error: Set needs to be specified')

        with patch.object(ipset, '_ipset_cmd', return_value='A'):
            mock = MagicMock(return_value=True)
            with patch.dict(ipset.__salt__, {'cmd.run': mock}):
                self.assertTrue(ipset.delete_set('set', 'family'))

    def test_rename_set(self):
        '''
        Test for Delete ipset set.
        '''
        self.assertEqual(ipset.rename_set(),
                         'Error: Set needs to be specified')

        self.assertEqual(ipset.rename_set('s'),
                         'Error: New name for set needs to be specified')

        with patch.object(ipset, '_find_set_type', return_value=False):
            self.assertEqual(ipset.rename_set('s', 'd'),
                             'Error: Set does not exist')

        with patch.object(ipset, '_find_set_type', return_value=True):
            self.assertEqual(ipset.rename_set('s', 'd'),
                             'Error: New Set already exists')

        with patch.object(ipset, '_find_set_type', side_effect=[True, False]):
            with patch.object(ipset, '_ipset_cmd', return_value='A'):
                mock = MagicMock(return_value=True)
                with patch.dict(ipset.__salt__, {'cmd.run': mock}):
                    self.assertTrue(ipset.rename_set('set', 'new_set'))

    def test_list_sets(self):
        '''
        Test for List all ipset sets.
        '''
        with patch.object(ipset, '_ipset_cmd', return_value='A'):
            mock = MagicMock(return_value="A:a")
            with patch.dict(ipset.__salt__, {'cmd.run': mock}):
                self.assertEqual(ipset.list_sets(), [{'A': ''}])

    def test_check_set(self):
        '''
        Test for Check that given ipset set exists.
        '''
        self.assertEqual(ipset.check_set(), 'Error: Set needs to be specified')

        with patch.object(ipset, '_find_set_info', side_effect=[False, True]):
            self.assertFalse(ipset.check_set('set'))
            self.assertTrue(ipset.check_set('set'))

    def test_add(self):
        '''
        Test for Append an entry to the specified set.
        '''
        self.assertEqual(ipset.add(), 'Error: Set needs to be specified')

        self.assertEqual(ipset.add('set'),
                         'Error: Entry needs to be specified')

        with patch.object(ipset, '_find_set_info', return_value=None):
            self.assertEqual(ipset.add('set', 'entry'),
                             'Error: Set set does not exist')

        mock = MagicMock(return_value={'Type': 'type',
                                       'Header': 'Header'})
        with patch.object(ipset, '_find_set_info', mock):
            self.assertEqual(ipset.add('set', 'entry', timeout=0),
                             'Error: Set set not created with timeout support')

            self.assertEqual(ipset.add('set', 'entry', packets=0),
                             'Error: Set set not created with \
counters support')

            self.assertEqual(ipset.add('set', 'entry', comment=0),
                             'Error: Set set not created with \
comment support')

        mock = MagicMock(return_value={'Type': 'bitmap:ip',
                                       'Header': 'Header'})
        with patch.object(ipset, '_find_set_info', mock):
            with patch.object(ipset, '_find_set_members', return_value='entry'):
                self.assertEqual(ipset.add('set', 'entry'),
                                 'Warn: Entry entry already exists in set set')

            with patch.object(ipset, '_find_set_members', return_value='A'):
                mock = MagicMock(return_value='')
                with patch.dict(ipset.__salt__, {'cmd.run': mock}):
                    self.assertEqual(ipset.add('set', 'entry'), 'Success')

                mock = MagicMock(return_value='out')
                with patch.dict(ipset.__salt__, {'cmd.run': mock}):
                    self.assertEqual(ipset.add('set', 'entry'), 'Error: out')

    def test_delete(self):
        '''
        Test for Delete an entry from the specified set.
        '''
        self.assertEqual(ipset.delete(), 'Error: Set needs to be specified')

        self.assertEqual(ipset.delete('s'),
                         'Error: Entry needs to be specified')

        with patch.object(ipset, '_find_set_type', return_value=None):
            self.assertEqual(ipset.delete('set', 'entry'),
                             'Error: Set set does not exist')

        with patch.object(ipset, '_find_set_type', return_value=True):
            with patch.object(ipset, '_ipset_cmd', return_value='A'):
                mock = MagicMock(side_effect=['', 'A'])
                with patch.dict(ipset.__salt__, {'cmd.run': mock}):
                    self.assertEqual(ipset.delete('set', 'entry'), 'Success')
                    self.assertEqual(ipset.delete('set', 'entry'), 'Error: A')

    def test_check(self):
        '''
        Test for Check that an entry exists in the specified set.
        '''
        self.assertEqual(ipset.check(), 'Error: Set needs to be specified')

        self.assertEqual(ipset.check('s'),
                         'Error: Entry needs to be specified')

        with patch.object(ipset, '_find_set_type', return_value=None):
            self.assertEqual(ipset.check('set', 'entry'),
                             'Error: Set set does not exist')

        with patch.object(ipset, '_find_set_type', return_value='hash:ip'):
            with patch.object(ipset, '_find_set_members',
                              side_effect=['entry', '',
                                           ['192.168.0.4', '192.168.0.5'],
                                           ['192.168.0.3'], ['192.168.0.6'],
                                           ['192.168.0.4', '192.168.0.5'],
                                           ['192.168.0.3'], ['192.168.0.6'],
                                           ]):
                self.assertTrue(ipset.check('set', 'entry'))
                self.assertFalse(ipset.check('set', 'entry'))
                self.assertTrue(ipset.check('set', '192.168.0.4/31'))
                self.assertFalse(ipset.check('set', '192.168.0.4/31'))
                self.assertFalse(ipset.check('set', '192.168.0.4/31'))
                self.assertTrue(ipset.check('set', '192.168.0.4-192.168.0.5'))
                self.assertFalse(ipset.check('set', '192.168.0.4-192.168.0.5'))
                self.assertFalse(ipset.check('set', '192.168.0.4-192.168.0.5'))

        with patch.object(ipset, '_find_set_type', return_value='hash:net'):
            with patch.object(ipset, '_find_set_members',
                              side_effect=['entry', '',
                                           '192.168.0.4/31', '192.168.0.4/30',
                                           '192.168.0.4/31', '192.168.0.4/30',
                                           ]):
                self.assertTrue(ipset.check('set', 'entry'))
                self.assertFalse(ipset.check('set', 'entry'))
                self.assertTrue(ipset.check('set', '192.168.0.4/31'))
                self.assertFalse(ipset.check('set', '192.168.0.4/31'))
                self.assertTrue(ipset.check('set', '192.168.0.4-192.168.0.5'))
                self.assertFalse(ipset.check('set', '192.168.0.4-192.168.0.5'))

    def test_test(self):
        '''
        Test for Test if an entry is in the specified set.
        '''
        self.assertEqual(ipset.test(), 'Error: Set needs to be specified')

        self.assertEqual(ipset.test('s'),
                         'Error: Entry needs to be specified')

        with patch.object(ipset, '_find_set_type', return_value=None):
            self.assertEqual(ipset.test('set', 'entry'),
                             'Error: Set set does not exist')

        with patch.object(ipset, '_find_set_type', return_value=True):
            mock = MagicMock(side_effect=[{'retcode': 1}, {'retcode': -1}])
            with patch.dict(ipset.__salt__, {'cmd.run_all': mock}):
                self.assertFalse(ipset.test('set', 'entry'))
                self.assertTrue(ipset.test('set', 'entry'))

    def test_flush(self):
        '''
        Test for Flush entries in the specified set
        '''
        with patch.object(ipset, '_find_set_type', return_value=None):
            self.assertEqual(ipset.flush('set'),
                             'Error: Set set does not exist')

        with patch.object(ipset, '_find_set_type', return_value=True):
            mock = MagicMock(side_effect=['', 'A'])
            with patch.dict(ipset.__salt__, {'cmd.run': mock}):
                self.assertTrue(ipset.flush('set'))
                self.assertFalse(ipset.flush('set'))
