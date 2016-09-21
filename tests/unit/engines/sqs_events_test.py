# -*- coding: utf-8 -*-
'''
unit tests for the sqs_events engine
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
from salt.engines import sqs_events

sqs_events.__salt__ = {}
sqs_events.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.engines.sqs_events.boto.sqs')
class EngineSqsEventTestCase(TestCase):
    '''
    Test cases for salt.engine.sqs_events
    '''
    def sample_msg(self):
        fake_msg = MagicMock()
        fake_msg.get_body.return_value = "This is a test message"
        fake_msg.delete.return_value = True
        return fake_msg

    # 'present' function tests: 1
    @patch('salt.engines.sqs_events.log')
    @patch('time.sleep', return_value=None)
    def test_no_queue_present(self, mock_sleep, mock_logging, mock_sqs):
        '''
        Test to ensure the SQS engine logs a warning when queue not present
        '''
        q = None
        q_name = 'mysqs'
        mock_fire = MagicMock(return_value=True)
        sqs_events._process_queue(q, q_name, mock_fire)
        self.assertTrue(mock_logging.warning.called)
        self.assertFalse(mock_sqs.queue.Queue().get_messages.called)

    def test_minion_message_fires(self, mock_sqs):
        '''
        Test SQS engine correctly gets and fires messages on minion
        '''
        msgs = [self.sample_msg(), self.sample_msg()]
        mock_sqs.queue.Queue().get_messages.return_value = msgs
        q = mock_sqs.queue.Queue()
        q_name = 'mysqs'
        mock_event = MagicMock(return_value=True)
        mock_fire = MagicMock(return_value=True)
        with patch.dict(sqs_events.__salt__, {'event.send': mock_event}):
            sqs_events._process_queue(q, q_name, mock_fire)
            self.assertTrue(mock_sqs.queue.Queue().get_messages.called)
            self.assertTrue(all(x.delete.called for x in msgs))

    def test_master_message_fires(self, mock_sqs):
        '''
        Test SQS engine correctly gets and fires messages on master
        '''
        msgs = [self.sample_msg(), self.sample_msg()]
        mock_sqs.queue.Queue().get_messages.return_value = msgs
        q = mock_sqs.queue.Queue()
        q_name = 'mysqs'
        mock_fire = MagicMock(return_value=True)
        sqs_events._process_queue(q, q_name, mock_fire)
        self.assertTrue(mock_sqs.queue.Queue().get_messages.called, len(msgs))
        self.assertTrue(mock_fire.called, len(msgs))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(EngineSqsEventTestCase, needs_daemon=False)
