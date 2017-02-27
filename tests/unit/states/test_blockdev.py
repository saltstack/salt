# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import
import os

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
from salt.states import blockdev
import salt.utils

blockdev.__salt__ = {}
blockdev.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BlockdevTestCase(TestCase):
    '''
    Test cases for salt.states.blockdev
    '''
    # 'tuned' function tests: 1

    def test_tuned(self):
        '''
        Test to manage options of block device
        '''
        name = '/dev/vg/master-data'

        ret = {'name': name,
               'result': True,
               'changes': {},
               'comment': ''}

        comt = ('Changes to {0} cannot be applied. '
                'Not a block device. ').format(name)
        with patch.dict(blockdev.__salt__, {'file.is_blkdev': False}):
            ret.update({'comment': comt})
            self.assertDictEqual(blockdev.tuned(name), ret)

        comt = ('Changes to {0} will be applied '.format(name))
        with patch.dict(blockdev.__salt__, {'file.is_blkdev': True}):
            ret.update({'comment': comt, 'result': None})
            with patch.dict(blockdev.__opts__, {'test': True}):
                self.assertDictEqual(blockdev.tuned(name), ret)

    # 'formatted' function tests: 1

    def test_formatted(self):
        '''
        Test to manage filesystems of partitions.
        '''
        name = '/dev/vg/master-data'

        ret = {'name': name,
               'result': False,
               'changes': {},
               'comment': ''}

        with patch.object(os.path, 'exists', MagicMock(side_effect=[False, True,
                                                                    True, True,
                                                                    True])):
            comt = ('{0} does not exist'.format(name))
            ret.update({'comment': comt})
            self.assertDictEqual(blockdev.formatted(name), ret)

            mock_ext4 = MagicMock(return_value='ext4')

            # Test state return when block device is already in the correct state
            with patch.dict(blockdev.__salt__, {'cmd.run': mock_ext4}):
                comt = '{0} already formatted with ext4'.format(name)
                ret.update({'comment': comt, 'result': True})
                self.assertDictEqual(blockdev.formatted(name), ret)

            # Test state return when provided block device is an invalid fs_type
            with patch.dict(blockdev.__salt__, {'cmd.run': MagicMock(return_value='')}):
                ret.update({'comment': 'Invalid fs_type: foo-bar',
                            'result': False})
                with patch.object(salt.utils, 'which',
                                  MagicMock(return_value=False)):
                    self.assertDictEqual(blockdev.formatted(name, fs_type='foo-bar'), ret)

            # Test state return when provided block device state will change and test=True
            with patch.dict(blockdev.__salt__, {'cmd.run': MagicMock(return_value='new-thing')}):
                comt = ('Changes to {0} will be applied '.format(name))
                ret.update({'comment': comt, 'result': None})
                with patch.object(salt.utils, 'which',
                                  MagicMock(return_value=True)):
                    with patch.dict(blockdev.__opts__, {'test': True}):
                        self.assertDictEqual(blockdev.formatted(name), ret)

            # Test state return when block device format fails
            with patch.dict(blockdev.__salt__, {'cmd.run': MagicMock(return_value=mock_ext4),
                                                'disk.format_': MagicMock(return_value=True)}):
                comt = ('Failed to format {0}'.format(name))
                ret.update({'comment': comt, 'result': False})
                with patch.object(salt.utils, 'which',
                                  MagicMock(return_value=True)):
                    with patch.dict(blockdev.__opts__, {'test': False}):
                        self.assertDictEqual(blockdev.formatted(name), ret)
