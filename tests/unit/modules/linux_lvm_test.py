# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import
import os.path

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import linux_lvm
from salt.exceptions import CommandExecutionError

# Globals
linux_lvm.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LinuxLVMTestCase(TestCase):
    '''
    TestCase for the salt.modules.linux_lvm module
    '''

    def test_version(self):
        '''
        Tests LVM version info from lvm version
        '''
        mock = MagicMock(return_value='Library version : 1')
        with patch.dict(linux_lvm.__salt__, {'cmd.run': mock}):
            self.assertEqual(linux_lvm.version(), '1')

    def test_fullversion(self):
        '''
        Tests all version info from lvm version
        '''
        mock = MagicMock(return_value='Library version : 1')
        with patch.dict(linux_lvm.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(linux_lvm.fullversion(),
                                 {'Library version': '1'})

    def test_pvdisplay(self):
        '''
        Tests information about the physical volume(s)
        '''
        mock = MagicMock(return_value={'retcode': 1})
        with patch.dict(linux_lvm.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(linux_lvm.pvdisplay(), {})

        mock = MagicMock(return_value={'retcode': 0,
                                       'stdout': 'A:B:C:D:E:F:G:H:I:J:K'})
        with patch.dict(linux_lvm.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(linux_lvm.pvdisplay(),
                                 {'A': {'Allocated Physical Extents': 'K',
                                        'Current Logical Volumes Here': 'G',
                                        'Free Physical Extents': 'J',
                                        'Internal Physical Volume Number': 'D',
                                        'Physical Extent Size (kB)': 'H',
                                        'Physical Volume (not) Allocatable': 'F',
                                        'Physical Volume Device': 'A',
                                        'Physical Volume Size (kB)': 'C',
                                        'Physical Volume Status': 'E',
                                        'Total Physical Extents': 'I',
                                        'Volume Group Name': 'B'}})

            mockpath = MagicMock(return_value='Z')
            with patch.object(os.path, 'realpath', mockpath):
                self.assertDictEqual(linux_lvm.pvdisplay(real=True),
                                     {'Z': {'Allocated Physical Extents': 'K',
                                            'Current Logical Volumes Here': 'G',
                                            'Free Physical Extents': 'J',
                                            'Internal Physical Volume Number': 'D',
                                            'Physical Extent Size (kB)': 'H',
                                            'Physical Volume (not) Allocatable': 'F',
                                            'Physical Volume Device': 'A',
                                            'Physical Volume Size (kB)': 'C',
                                            'Physical Volume Status': 'E',
                                            'Real Physical Volume Device': 'Z',
                                            'Total Physical Extents': 'I',
                                            'Volume Group Name': 'B'}})

    def test_vgdisplay(self):
        '''
        Tests information about the volume group(s)
        '''
        mock = MagicMock(return_value={'retcode': 1})
        with patch.dict(linux_lvm.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(linux_lvm.vgdisplay(), {})

        mock = MagicMock(return_value={'retcode': 0,
                                       'stdout': 'A:B:C:D:E:F:G:H:I:J:K:L:M:N:O:P:Q'})
        with patch.dict(linux_lvm.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(linux_lvm.vgdisplay(),
                                 {'A': {'Actual Physical Volumes': 'K',
                                        'Allocated Physical Extents': 'O',
                                        'Current Logical Volumes': 'F',
                                        'Current Physical Volumes': 'J',
                                        'Free Physical Extents': 'P',
                                        'Internal Volume Group Number': 'D',
                                        'Maximum Logical Volume Size': 'H',
                                        'Maximum Logical Volumes': 'E',
                                        'Maximum Physical Volumes': 'I',
                                        'Open Logical Volumes': 'G',
                                        'Physical Extent Size (kB)': 'M',
                                        'Total Physical Extents': 'N',
                                        'UUID': 'Q',
                                        'Volume Group Access': 'B',
                                        'Volume Group Name': 'A',
                                        'Volume Group Size (kB)': 'L',
                                        'Volume Group Status': 'C'}})

    def test__lvdisplay(self):
        '''
        Return information about the logical volume(s)
        '''
        mock = MagicMock(return_value={'retcode': 1})
        with patch.dict(linux_lvm.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(linux_lvm.lvdisplay(), {})

        mock = MagicMock(return_value={'retcode': 0,
                                       'stdout': 'A:B:C:D:E:F:G:H:I:J:K:L:M'})
        with patch.dict(linux_lvm.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(linux_lvm.lvdisplay(),
                                 {'A': {'Allocated Logical Extents': 'I',
                                        'Allocation Policy': 'J',
                                        'Current Logical Extents Associated': 'H',
                                        'Internal Logical Volume Number': 'E',
                                        'Logical Volume Access': 'C',
                                        'Logical Volume Name': 'A',
                                        'Logical Volume Size': 'G',
                                        'Logical Volume Status': 'D',
                                        'Major Device Number': 'L',
                                        'Minor Device Number': 'M',
                                        'Open Logical Volumes': 'F',
                                        'Read Ahead Sectors': 'K',
                                        'Volume Group Name': 'B'}})

    def test_pvcreate(self):
        '''
        Tests for set a physical device to be used as an LVM physical volume
        '''
        self.assertEqual(linux_lvm.pvcreate(''),
                         'Error: at least one device is required')

        self.assertRaises(CommandExecutionError, linux_lvm.pvcreate, 'A')

        pvdisplay = MagicMock(return_value=True)
        with patch('salt.modules.linux_lvm.pvdisplay', pvdisplay):
            with patch.object(os.path, 'exists', return_value=True):
                ret = {'stdout': 'saltines', 'stderr': 'cheese', 'retcode': 0, 'pid': '1337'}
                mock = MagicMock(return_value=ret)
                with patch.dict(linux_lvm.__salt__, {'cmd.run_all': mock}):
                    self.assertEqual(linux_lvm.pvcreate('A', metadatasize=1000), True)

    def test_pvremove(self):
        '''
        Tests for remove a physical device being used as an LVM physical volume
        '''
        pvdisplay = MagicMock(return_value=False)
        with patch('salt.modules.linux_lvm.pvdisplay', pvdisplay):
            self.assertRaises(CommandExecutionError, linux_lvm.pvremove, 'A', override=False)

        pvdisplay = MagicMock(return_value=False)
        with patch('salt.modules.linux_lvm.pvdisplay', pvdisplay):
            mock = MagicMock(return_value=True)
            with patch.dict(linux_lvm.__salt__, {'lvm.pvdisplay': mock}):
                ret = {'stdout': 'saltines', 'stderr': 'cheese', 'retcode': 0, 'pid': '1337'}
                mock = MagicMock(return_value=ret)
                with patch.dict(linux_lvm.__salt__, {'cmd.run_all': mock}):
                    self.assertEqual(linux_lvm.pvremove('A'), True)

    def test_vgcreate(self):
        '''
        Tests create an LVM volume group
        '''
        self.assertEqual(linux_lvm.vgcreate('', ''),
                         'Error: vgname and device(s) are both required')

        mock = MagicMock(return_value='A\nB')
        with patch.dict(linux_lvm.__salt__, {'cmd.run': mock}):
            with patch.object(linux_lvm, 'vgdisplay', return_value={}):
                self.assertDictEqual(linux_lvm.vgcreate('A', 'B'),
                                     {'Output from vgcreate': 'A'})

    def test_vgextend(self):
        '''
        Tests add physical volumes to an LVM volume group
        '''
        self.assertEqual(linux_lvm.vgextend('', ''),
                         'Error: vgname and device(s) are both required')

        mock = MagicMock(return_value='A\nB')
        with patch.dict(linux_lvm.__salt__, {'cmd.run': mock}):
            with patch.object(linux_lvm, 'vgdisplay', return_value={}):
                self.assertDictEqual(linux_lvm.vgextend('A', 'B'),
                                     {'Output from vgextend': 'A'})

    def test_lvcreate(self):
        '''
        Test create a new logical volume, with option
        for which physical volume to be used
        '''
        self.assertEqual(linux_lvm.lvcreate(None, None, 1, 1),
                         'Error: Please specify only one of size or extents')

        self.assertEqual(linux_lvm.lvcreate(None, None, None, None),
                         'Error: Either size or extents must be specified')

        mock = MagicMock(return_value='A\nB')
        with patch.dict(linux_lvm.__salt__, {'cmd.run': mock}):
            with patch.object(linux_lvm, 'lvdisplay', return_value={}):
                self.assertDictEqual(linux_lvm.lvcreate(None, None, None, 1),
                                     {'Output from lvcreate': 'A'})

    def test_vgremove(self):
        '''
        Tests to remove an LVM volume group
        '''
        mock = MagicMock(return_value='A')
        with patch.dict(linux_lvm.__salt__, {'cmd.run': mock}):
            self.assertEqual(linux_lvm.vgremove('A'), 'A')

    def test_lvremove(self):
        '''
        Test to remove a given existing logical volume
        from a named existing volume group
        '''
        mock = MagicMock(return_value='A')
        with patch.dict(linux_lvm.__salt__, {'cmd.run': mock}):
            self.assertEqual(linux_lvm.lvremove('', ''), 'A')

    def test_lvresize(self):
        '''
        Test to return information about the logical volume(s)
        '''
        mock = MagicMock(return_value={'retcode': 1})
        with patch.dict(linux_lvm.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(linux_lvm.lvresize(1, 'a'), {})

        mock = MagicMock(return_value={'retcode': 0})
        with patch.dict(linux_lvm.__salt__, {'cmd.run_all': mock}):
            self.assertDictEqual(linux_lvm.lvresize(1, 'a'), {})

if __name__ == '__main__':
    from integration import run_tests
    run_tests(LinuxLVMTestCase, needs_daemon=False)
