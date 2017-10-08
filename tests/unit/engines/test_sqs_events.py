# -*- coding: utf-8 -*-
'''
unit tests for the sqs_events engine
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
import salt.engines.sqs_events as sqs_events


@skipIf(sqs_events.HAS_BOTO is False, 'The boto library is not installed')
@skipIf(NO_MOCK, NO_MOCK_REASON)
class EngineSqsEventTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.engine.sqs_events
    '''

    def setup_loader_modules(self):
        patcher = patch('salt.engines.sqs_events.boto.sqs')
        self.mock_sqs = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(delattr, self, 'mock_sqs')
        return {sqs_events: {}}

    def sample_msg(self):
        fake_msg = MagicMock()
        fake_msg.get_body.return_value = "This is a test message"
        fake_msg.delete.return_value = True
        return fake_msg

    # 'present' function tests: 1
    def test_no_queue_present(self):
        '''
        Test to ensure the SQS engine logs a warning when queue not present
        '''
        with patch('salt.engines.sqs_events.log') as mock_logging:
            with patch('time.sleep', return_value=None) as mock_sleep:
                q = None
                q_name = 'mysqs'
                mock_fire = MagicMock(return_value=True)
                sqs_events._process_queue(q, q_name, mock_fire)
                self.assertTrue(mock_logging.warning.called)
                self.assertFalse(self.mock_sqs.queue.Queue().get_messages.called)

    def test_minion_message_fires(self):
        '''
        Test SQS engine correctly gets and fires messages on minion
        '''
        msgs = [self.sample_msg(), self.sample_msg()]
        self.mock_sqs.queue.Queue().get_messages.return_value = msgs
        q = self.mock_sqs.queue.Queue()
        q_name = 'mysqs'
        mock_event = MagicMock(return_value=True)
        mock_fire = MagicMock(return_value=True)
        with patch.dict(sqs_events.__salt__, {'event.send': mock_event}):
            sqs_events._process_queue(q, q_name, mock_fire)
            self.assertTrue(self.mock_sqs.queue.Queue().get_messages.called)
            self.assertTrue(all(x.delete.called for x in msgs))

    def test_master_message_fires(self):
        '''
        Test SQS engine correctly gets and fires messages on master
        '''
        msgs = [self.sample_msg(), self.sample_msg()]
        self.mock_sqs.queue.Queue().get_messages.return_value = msgs
        q = self.mock_sqs.queue.Queue()
        q_name = 'mysqs'
        mock_fire = MagicMock(return_value=True)
        sqs_events._process_queue(q, q_name, mock_fire)
        self.assertTrue(self.mock_sqs.queue.Queue().get_messages.called, len(msgs))
        self.assertTrue(mock_fire.called, len(msgs))
