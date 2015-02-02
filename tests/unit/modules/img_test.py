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
from salt.modules import img

# Globals
img.__salt__ = {}
img.__context__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ImgTestCase(TestCase):
    '''
    Test cases for salt.modules.img
    '''
    def test_mount_image(self):
        '''
        Test for Mount the named image and return the mount point
        '''
        mock = MagicMock(return_value='A')
        with patch.dict(img.__salt__, {'guestfs.mount': mock}):
            self.assertEqual(img.mount_image('location'), 'A')

        mock = MagicMock(side_effect=[{}, {'A': 'A', 'B': 'B'}])
        with patch.dict(img.__salt__, {'qemu_nbd.init': mock}):
            self.assertEqual(img.mount_image('location'), '')

            self.assertEqual(img.mount_image('location'), 'A')

        mock = MagicMock(return_value=None)
        with patch.dict(img.__salt__, mock):
            self.assertEqual(img.mount_image('location'), '')

    def test_umount_image(self):
        '''
        Test for Unmount an image mountpoint
        '''
        mock = MagicMock(return_value='A')
        with patch.dict(img.__salt__, {'qemu_nbd.clear': mock}):
            mock = MagicMock(return_value='B')
            with patch.dict(img.__context__, {'img.mnt_mnt': mock}):
                self.assertEqual(img.umount_image('mnt'), None)

    def test_bootstrap(self):
        '''
        Test for HIGHLY EXPERIMENTAL
        '''
        mock = MagicMock(return_value=None)
        with patch.dict(img.__salt__, {'img.make_image': mock}):
            self.assertEqual(img.bootstrap('location', 'size', 'fmt'), '')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(ImgTestCase, needs_daemon=False)
