# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import os.path
import glob

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
from salt.modules import qemu_nbd

qemu_nbd.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class QemuNbdTestCase(TestCase):
    '''
    Test cases for salt.modules.qemu_nbd
    '''
    # 'connect' function tests: 1

    def test_connect(self):
        '''
        Test if it activate nbd for an image file.
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(qemu_nbd.__salt__, {'cmd.run': mock}):
            with patch.object(os.path, 'isfile',
                              MagicMock(return_value=False)):
                self.assertEqual(qemu_nbd.connect('/tmp/image.raw'), '')
                self.assertEqual(qemu_nbd.connect('/tmp/image.raw'), '')

        with patch.object(os.path, 'isfile', mock):
            with patch.object(glob, 'glob',
                              MagicMock(return_value=['/dev/nbd0'])):
                with patch.dict(qemu_nbd.__salt__,
                                {'cmd.run': mock,
                                 'cmd.retcode': MagicMock(side_effect=[1, 0])}):
                    self.assertEqual(qemu_nbd.connect('/tmp/image.raw'),
                                     '/dev/nbd0')

                with patch.dict(qemu_nbd.__salt__,
                                {'cmd.run': mock,
                                 'cmd.retcode': MagicMock(return_value=False)}):
                    self.assertEqual(qemu_nbd.connect('/tmp/image.raw'), '')

    # 'mount' function tests: 1

    def test_mount(self):
        '''
        Test if it pass in the nbd connection device location,
        mount all partitions and return a dict of mount points.
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(qemu_nbd.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(qemu_nbd.mount('/dev/nbd0'), {})

    # 'init' function tests: 1

    def test_init(self):
        '''
        Test if it mount the named image via qemu-nbd
        and return the mounted roots
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(qemu_nbd.__salt__, {'cmd.run': mock}):
            self.assertEqual(qemu_nbd.init('/srv/image.qcow2'), '')

        with patch.object(os.path, 'isfile', mock):
            with patch.object(glob, 'glob',
                              MagicMock(return_value=['/dev/nbd0'])):
                with patch.dict(qemu_nbd.__salt__,
                                {'cmd.run': mock,
                                 'mount.mount': mock,
                                 'cmd.retcode': MagicMock(side_effect=[1, 0])}):
                    self.assertDictEqual(qemu_nbd.init('/srv/image.qcow2'),
                                         {'/tmp/nbd/nbd0/nbd0': '/dev/nbd0'})

    # 'clear' function tests: 1

    def test_clear(self):
        '''
        Test if it pass in the mnt dict returned from nbd_mount
        to unmount and disconnect the image from nbd.
        '''
        mock_run = MagicMock(return_value=True)
        with patch.dict(qemu_nbd.__salt__,
                        {'cmd.run': mock_run,
                         'mount.umount': MagicMock(side_effect=[False, True])}):
            self.assertDictEqual(qemu_nbd.clear({"/mnt/foo": "/dev/nbd0p1"}),
                                 {'/mnt/foo': '/dev/nbd0p1'})
            self.assertDictEqual(qemu_nbd.clear({"/mnt/foo": "/dev/nbd0p1"}),
                                 {})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(QemuNbdTestCase, needs_daemon=False)
