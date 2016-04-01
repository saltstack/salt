# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import genesis


# Globals
genesis.__grains__ = {}
genesis.__salt__ = {}
genesis.__context__ = {}
genesis.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GenesisTestCase(TestCase):
    '''
    Test cases for salt.modules.genesis
    '''
    def test_bootstrap(self):
        '''
        Test for Create an image for a specific platform.
        '''
        mock = MagicMock(return_value=False)
        with patch.dict(genesis.__salt__, {'file.directory_exists': mock}):
            mock = MagicMock(side_effect=Exception('foo'))
            with patch.dict(genesis.__salt__, {'file.mkdir': mock}):
                self.assertEqual(genesis.bootstrap('platform', 'root'),
                                 {'Error': "Exception('foo',)"})

        with patch.object(genesis, '_bootstrap_yum', return_value='A'):
            self.assertEqual(genesis.bootstrap('rpm', 'root', 'dir1'), 'A')

        with patch.object(genesis, '_bootstrap_deb', return_value='A'):
            self.assertEqual(genesis.bootstrap('deb', 'root', 'dir1'), 'A')

        with patch.object(genesis, '_bootstrap_pacman', return_value='A'):
            self.assertEqual(genesis.bootstrap('pacman', 'root', 'dir1'), 'A')

    @patch('salt.utils.which', MagicMock(return_value=False))
    def test_avail_platforms(self):
        '''
        Test for Return which platforms are available
        '''
        self.assertFalse(genesis.avail_platforms()['deb'])

    def test_pack(self):
        '''
        Test for Pack up a directory structure, into a specific format
        '''
        with patch.object(genesis, '_tar', return_value='tar'):
            self.assertEqual(genesis.pack('name', 'root'), None)

    def test_unpack(self):
        '''
        Test for Unpack an image into a directory structure
        '''
        with patch.object(genesis, '_untar', return_value='untar'):
            self.assertEqual(genesis.unpack('name', 'root'), None)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GenesisTestCase, needs_daemon=False)
