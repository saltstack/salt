# -*- coding: utf-8 -*-
'''
Tests for disk state
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.states import disk

disk.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DiskTestCase(TestCase):
    '''
    Test disk state
    '''
    def setUp(self):
        '''
        setup common test info
        '''
        self.mock_data = {
            '/': {
                '1K-blocks': '41147472',
                'available': '37087976',
                'capacity': '6%',
                'filesystem': '/dev/xvda1',
                'used': '2172880'},
            '/dev': {
                '1K-blocks': '10240',
                'available': '10240',
                'capacity': '0%',
                'filesystem': 'udev',
                'used': '0'},
            '/run': {
                '1K-blocks': '410624',
                'available': '379460',
                'capacity': '8%',
                'filesystem': 'tmpfs',
                'used': '31164'},
            '/sys/fs/cgroup': {
                '1K-blocks': '1026556',
                'available': '1026556',
                'capacity': '0%',
                'filesystem': 'tmpfs',
                'used': '0'}
        }
        self.__salt__ = {
            'disk.usage': MagicMock(return_value=self.mock_data),
        }

    def test_status_missing(self):
        '''
        Test disk.status when name not found
        '''
        mock_fs = '/mnt/cheese'
        mock_ret = {'name': mock_fs,
                    'result': False,
                    'comment': 'Named disk mount not present ',
                    'changes': {},
                    'data': {}}

        with patch.dict(disk.__salt__, self.__salt__):
            ret = disk.status(mock_fs)
            self.assertEqual(ret, mock_ret)

    def test_status_type_error(self):
        '''
        Test disk.status with incorrectly formatted arguments
        '''
        mock_fs = '/'
        mock_ret = {'name': mock_fs,
                    'result': False,
                    'comment': 'maximum must be an integer ',
                    'changes': {},
                    'data': {}}

        with patch.dict(disk.__salt__, self.__salt__):
            ret = disk.status(mock_fs, maximum=r'e^{i\pi}')
            self.assertEqual(ret, mock_ret)

        with patch.dict(disk.__salt__, self.__salt__):
            mock_ret['comment'] = 'minimum must be an integer '
            ret = disk.status(mock_fs, minimum=r'\cos\pi + i\sin\pi')
            self.assertEqual(ret, mock_ret)

    def test_status_range_error(self):
        '''
        Test disk.status with excessive extrema
        '''
        mock_fs = '/'
        mock_ret = {'name': mock_fs,
                    'result': False,
                    'comment': 'maximum must be in the range [0, 100] ',
                    'changes': {},
                    'data': {}}

        with patch.dict(disk.__salt__, self.__salt__):
            ret = disk.status(mock_fs, maximum='-1')
            self.assertEqual(ret, mock_ret)

        with patch.dict(disk.__salt__, self.__salt__):
            mock_ret['comment'] = 'minimum must be in the range [0, 100] '
            ret = disk.status(mock_fs, minimum='101')
            self.assertEqual(ret, mock_ret)

    def test_status_inverted_range(self):
        '''
        Test disk.status when minimum > maximum
        '''
        mock_fs = '/'
        mock_ret = {'name': mock_fs,
                    'result': False,
                    'comment': 'Min must be less than max ',
                    'changes': {},
                    'data': {}}

        with patch.dict(disk.__salt__, self.__salt__):
            ret = disk.status(mock_fs, maximum='0', minimum='1')
            self.assertEqual(ret, mock_ret)

    def test_status_threshold(self):
        '''
        Test disk.status when filesystem triggers thresholds
        '''
        mock_min = 100
        mock_max = 0
        mock_fs = '/'
        mock_used = int(self.mock_data[mock_fs]['capacity'].strip('%'))
        mock_ret = {'name': mock_fs,
                    'result': False,
                    'comment': '',
                    'changes': {},
                    'data': self.mock_data[mock_fs]}

        with patch.dict(disk.__salt__, self.__salt__):
            mock_ret['comment'] = 'Disk used space is below minimum of {0}% at {1}%'.format(
                                       mock_min,
                                       mock_used
                                   )
            ret = disk.status(mock_fs, minimum=mock_min)
            self.assertEqual(ret, mock_ret)

        with patch.dict(disk.__salt__, self.__salt__):
            mock_ret['comment'] = 'Disk used space is above maximum of {0}% at {1}%'.format(
                                       mock_max,
                                       mock_used
                                   )
            ret = disk.status(mock_fs, maximum=mock_max)
            self.assertEqual(ret, mock_ret)

    def test_status(self):
        '''
        Test disk.status when filesystem meets thresholds
        '''
        mock_min = 0
        mock_max = 100
        mock_fs = '/'
        mock_ret = {'name': mock_fs,
                    'result': True,
                    'comment': 'Disk in acceptable range',
                    'changes': {},
                    'data': self.mock_data[mock_fs]}

        with patch.dict(disk.__salt__, self.__salt__):
            ret = disk.status(mock_fs, minimum=mock_min)
            self.assertEqual(ret, mock_ret)

        with patch.dict(disk.__salt__, self.__salt__):
            ret = disk.status(mock_fs, maximum=mock_max)
            self.assertEqual(ret, mock_ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DiskTestCase, needs_daemon=False)
