# -*- coding: utf-8 -*-
'''
Tests for disk state
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

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
                    'comment': '',
                    'changes': {},
                    'data': {}}

        with patch.dict(disk.__salt__, self.__salt__):
            mock_ret['comment'] = 'maximum must be an integer '
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
                    'comment': '',
                    'changes': {},
                    'data': {}}

        with patch.dict(disk.__salt__, self.__salt__):
            mock_ret['comment'] = 'maximum must be in the range [0, 100] '
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
                    'comment': 'minimum must be less than maximum ',
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
            mock_ret['comment'] = 'Disk used space is below minimum of {0} % at {1} %'.format(
                                       mock_min,
                                       mock_used
                                   )
            ret = disk.status(mock_fs, minimum=mock_min)
            self.assertEqual(ret, mock_ret)

        with patch.dict(disk.__salt__, self.__salt__):
            mock_ret['comment'] = 'Disk used space is above maximum of {0} % at {1} %'.format(
                                       mock_max,
                                       mock_used
                                   )
            ret = disk.status(mock_fs, maximum=mock_max)
            self.assertEqual(ret, mock_ret)

    def test_status_strip(self):
        '''
        Test disk.status appropriately strips unit info from numbers
        '''
        mock_fs = '/'
        mock_ret = {'name': mock_fs,
                    'result': True,
                    'comment': 'Disk used space in acceptable range',
                    'changes': {},
                    'data': self.mock_data[mock_fs]}

        with patch.dict(disk.__salt__, self.__salt__):
            ret = disk.status(mock_fs, minimum='0%')
            self.assertEqual(ret, mock_ret)

            ret = disk.status(mock_fs, minimum='0 %')
            self.assertEqual(ret, mock_ret)

            ret = disk.status(mock_fs, maximum='100%')
            self.assertEqual(ret, mock_ret)

            ret = disk.status(mock_fs, minimum='1024K', absolute=True)
            self.assertEqual(ret, mock_ret)

            ret = disk.status(mock_fs, minimum='1024KB', absolute=True)
            self.assertEqual(ret, mock_ret)

            ret = disk.status(mock_fs, maximum='4194304 KB', absolute=True)
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
                    'comment': 'Disk used space in acceptable range',
                    'changes': {},
                    'data': self.mock_data[mock_fs]}

        with patch.dict(disk.__salt__, self.__salt__):
            ret = disk.status(mock_fs, minimum=mock_min)
            self.assertEqual(ret, mock_ret)

        with patch.dict(disk.__salt__, self.__salt__):
            ret = disk.status(mock_fs, maximum=mock_max)
            self.assertEqual(ret, mock_ret)

        # Reset mock because it's an iterator to run the tests with the
        # absolute flag
        ret = {'name': mock_fs,
               'result': False,
               'comment': '',
               'changes': {},
               'data': {}}

        mock = MagicMock(side_effect=[[], [mock_fs], {mock_fs: {'capacity': '8 %', 'used': '8'}},
            {mock_fs: {'capacity': '22 %', 'used': '22'}},
            {mock_fs: {'capacity': '15 %', 'used': '15'}}])
        with patch.dict(disk.__salt__, {'disk.usage': mock}):
            comt = ('Named disk mount not present ')
            ret.update({'comment': comt})
            self.assertDictEqual(disk.status(mock_fs), ret)

            comt = ('minimum must be less than maximum ')
            ret.update({'comment': comt})
            self.assertDictEqual(disk.status(mock_fs, '10', '20', absolute=True), ret)

            comt = ('Disk used space is below minimum of 10 KB at 8 KB')
            ret.update({'comment': comt, 'data': {'capacity': '8 %', 'used': '8'}})
            self.assertDictEqual(disk.status(mock_fs, '20', '10', absolute=True), ret)

            comt = ('Disk used space is above maximum of 20 KB at 22 KB')
            ret.update({'comment': comt, 'data': {'capacity': '22 %', 'used': '22'}})
            self.assertDictEqual(disk.status(mock_fs, '20', '10', absolute=True), ret)

            comt = ('Disk used space in acceptable range')
            ret.update({'comment': comt, 'result': True,
                'data': {'capacity': '15 %', 'used': '15'}})
            self.assertDictEqual(disk.status(mock_fs, '20', '10', absolute=True), ret)
