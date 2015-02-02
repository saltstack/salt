# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON

# Import Salt Libs
from salt.modules import extfs


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ExtfsTestCase(TestCase):
    '''
    TestCase for salt.modules.extfs
    '''
    extfs.__salt__ = {}

    # 'mkfs' function tests: 1

    def test_mkfs(self):
        '''
        Tests if a file system created on the specified device
        '''
        mock = MagicMock()
        with patch.dict(extfs.__salt__, {'cmd.run': mock}):
            self.assertListEqual([], extfs.mkfs('/dev/sda1', 'ext4'))

    # 'tune' function tests: 1

    @patch('salt.modules.extfs.tune', MagicMock(return_value=''))
    def test_tune(self):
        '''
        Tests if specified group was added
        '''
        mock = MagicMock()
        with patch.dict(extfs.__salt__, {'cmd.run': mock}):
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

    @patch('salt.modules.extfs.dump',
           MagicMock(return_value={'attributes': {}, 'blocks': {}}))
    def test_attributes(self):
        '''
        Tests if specified group was added
        '''
        self.assertEqual({}, extfs.attributes('/dev/sda1'))

    # 'blocks' function tests: 1

    @patch('salt.modules.extfs.dump',
           MagicMock(return_value={'attributes': {}, 'blocks': {}}))
    def test_blocks(self):
        '''
        Tests if specified group was added
        '''
        self.assertEqual({}, extfs.blocks('/dev/sda1'))

if __name__ == '__main__':
    from integration import run_tests
    run_tests(ExtfsTestCase, needs_daemon=False)
