# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
from salt.cli.batch import Batch

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import MagicMock, patch, NO_MOCK, NO_MOCK_REASON


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BatchTestCase(TestCase):
    '''
    Unit Tests for the salt.cli.batch module
    '''

    def setUp(self):
        opts = {'batch': '',
                'conf_file': {},
                'tgt': '',
                'transport': '',
                'timeout': 5,
                'gather_job_timeout': 5}

        mock_client = MagicMock()
        with patch('salt.client.get_local_client', MagicMock(return_value=mock_client)):
            with patch('salt.client.LocalClient.cmd_iter', MagicMock(return_value=[])):
                self.batch = Batch(opts, quiet='quiet')

    # get_bnum tests

    def test_get_bnum(self):
        '''
        Tests passing batch value as a number
        '''
        self.batch.opts = {'batch': '2', 'timeout': 5}
        self.batch.minions = ['foo', 'bar']
        self.assertEqual(Batch.get_bnum(self.batch), 2)

    def test_get_bnum_percentage(self):
        '''
        Tests passing batch value as percentage
        '''
        self.batch.opts = {'batch': '50%', 'timeout': 5}
        self.batch.minions = ['foo']
        self.assertEqual(Batch.get_bnum(self.batch), 1)

    def test_get_bnum_high_percentage(self):
        '''
        Tests passing batch value as percentage over 100%
        '''
        self.batch.opts = {'batch': '160%', 'timeout': 5}
        self.batch.minions = ['foo', 'bar', 'baz']
        self.assertEqual(Batch.get_bnum(self.batch), 4)

    def test_get_bnum_invalid_batch_data(self):
        '''
        Tests when an invalid batch value is passed
        '''
        ret = Batch.get_bnum(self.batch)
        self.assertEqual(ret, None)
