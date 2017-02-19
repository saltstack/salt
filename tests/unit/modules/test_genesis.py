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
from salt.modules import genesis


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GenesisTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.genesis
    '''
    loader_module = genesis

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
            with patch.dict(genesis.__salt__, {'mount.umount': MagicMock(),
                                               'file.rmdir': MagicMock(),
                                               'file.directory_exists': MagicMock()}):
                with patch.dict(genesis.__salt__, {'disk.blkid': MagicMock(return_value={})}):
                    self.assertEqual(genesis.bootstrap('rpm', 'root', 'dir'), None)

        with patch.object(genesis, '_bootstrap_deb', return_value='A'):
            with patch.dict(genesis.__salt__, {'mount.umount': MagicMock(),
                                               'file.rmdir': MagicMock(),
                                               'file.directory_exists': MagicMock()}):
                with patch.dict(genesis.__salt__, {'disk.blkid': MagicMock(return_value={})}):
                    self.assertEqual(genesis.bootstrap('deb', 'root', 'dir'), None)

        with patch.object(genesis, '_bootstrap_pacman', return_value='A') as pacman_patch:
            with patch.dict(genesis.__salt__, {'mount.umount': MagicMock(),
                                               'file.rmdir': MagicMock(),
                                               'file.directory_exists': MagicMock(),
                                               'disk.blkid': MagicMock(return_value={})}):
                genesis.bootstrap('pacman', 'root', 'dir')
                pacman_patch.assert_called_with('root', img_format='dir', exclude_pkgs=[], pkgs=[])

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
