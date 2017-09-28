# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

# Import Salt Libs
import salt.modules.extfs as extfs


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ExtfsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.extfs
    '''
    def setup_loader_modules(self):
        return {extfs: {}}

    # 'mkfs' function tests: 1

    def test_mkfs(self):
        '''
        Tests if a file system created on the specified device
        '''
        mock = MagicMock()
        with patch.dict(extfs.__salt__, {'cmd.run': mock}):
            self.assertListEqual([], extfs.mkfs('/dev/sda1', 'ext4'))

    # 'tune' function tests: 1

    def test_tune(self):
        '''
        Tests if specified group was added
        '''
        mock = MagicMock()
        with patch.dict(extfs.__salt__, {'cmd.run': mock}), \
                patch('salt.modules.extfs.tune', MagicMock(return_value='')):
            self.assertEqual('', extfs.tune('/dev/sda1'))

    # 'dump' function tests: 1

    def test_dump(self):
        '''
        Tests if specified group was added
        '''
        mock = MagicMock()
        with patch.dict(extfs.__salt__, {'cmd.run': mock}):
            self.assertEqual({'attributes': {}, 'blocks': {}},
                             extfs.dump('/dev/sda1'))

    # 'attributes' function tests: 1

    def test_attributes(self):
        '''
        Tests if specified group was added
        '''
        with patch('salt.modules.extfs.dump',
                    MagicMock(return_value={'attributes': {}, 'blocks': {}})):
            self.assertEqual({}, extfs.attributes('/dev/sda1'))

    # 'blocks' function tests: 1

    def test_blocks(self):
        '''
        Tests if specified group was added
        '''
        with patch('salt.modules.extfs.dump',
                   MagicMock(return_value={'attributes': {}, 'blocks': {}})):
            self.assertEqual({}, extfs.blocks('/dev/sda1'))
