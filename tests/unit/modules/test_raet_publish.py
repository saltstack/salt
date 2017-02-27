# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
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
from salt.modules import raet_publish
import salt.transport
from salt.exceptions import SaltReqTimeoutError

# Globals
raet_publish.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class RaetPublishTestCase(TestCase):
    '''
    Test cases for salt.modules.raet_publish
    '''
    def test_publish(self):
        '''
        Test for publish a command from the minion out to other minions.
        '''
        with patch.object(raet_publish, '_publish', return_value='A'):
            self.assertEqual(raet_publish.publish('tgt', 'fun'), 'A')

    def test_full_data(self):
        '''
        Test for return the full data about the publication,
         this is invoked in the same way as the publish function
        '''
        with patch.object(raet_publish, '_publish', return_value='A'):
            self.assertEqual(raet_publish.full_data('tgt', 'fun'), 'A')

    def test_runner(self):
        '''
        Test for execute a runner on the master and return
         the data from the runner function
        '''
        with patch.dict(raet_publish.__opts__, {'id': 'id'}):
            with patch.object(salt.transport.Channel, 'factory', MagicMock()):
                self.assertTrue(raet_publish.runner('fun'))

        class MockFactory(object):
            '''
            Mock factory class
            '''
            load = ''

            def send(self, load):
                '''
                mock send method
                '''
                self.load = load
                raise SaltReqTimeoutError(load)

        with patch.dict(raet_publish.__opts__, {'id': 'id'}):
            with patch.object(salt.transport.Channel, 'factory',
                              MagicMock(return_value=MockFactory())):
                self.assertEqual(raet_publish.runner(1),
                                 '\'1\' runner publish timed out')
