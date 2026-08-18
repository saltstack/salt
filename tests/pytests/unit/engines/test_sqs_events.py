"""
unit tests for the sqs_events engine
"""

import pytest

import salt.engines.sqs_events as sqs_events
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skipif(
        sqs_events.HAS_BOTO is False, reason="The boto library is not installed"
    )
]


@pytest.fixture
def configure_loader_modules():
    return {sqs_events: {}}


@pytest.fixture
def mock_sqs():
    with patch("salt.engines.sqs_events.boto.sqs") as mock_sqs:
        yield mock_sqs


def sample_msg():
    fake_msg = MagicMock()
    fake_msg.get_body.return_value = "This is a test message"
    fake_msg.delete.return_value = True
    return fake_msg


# 'present' function tests: 1
def test_no_queue_present(mock_sqs):
    """
    Test to ensure the SQS engine logs a warning when queue not present
    """
    with patch("salt.engines.sqs_events.log") as mock_logging:
        with patch("time.sleep", return_value=None) as mock_sleep:
            q = None
            q_name = "mysqs"
            mock_fire = MagicMock(return_value=True)
            sqs_events._process_queue(q, q_name, mock_fire)
            assert mock_logging.warning.called
            assert not mock_sqs.queue.Queue().get_messages.called


def test_minion_message_fires(mock_sqs):
    """
    Test SQS engine correctly gets and fires messages on minion
    """
    msgs = [sample_msg(), sample_msg()]
    mock_sqs.queue.Queue().get_messages.return_value = msgs
    q = mock_sqs.queue.Queue()
    q_name = "mysqs"
    mock_event = MagicMock(return_value=True)
    mock_fire = MagicMock(return_value=True)
    with patch.dict(sqs_events.__salt__, {"event.send": mock_event}):
        sqs_events._process_queue(q, q_name, mock_fire)
        assert mock_sqs.queue.Queue().get_messages.called
        assert all(x.delete.called for x in msgs)


def test_master_message_fires(mock_sqs):
    """
    Test SQS engine correctly gets and fires messages on master
    """
    msgs = [sample_msg(), sample_msg()]
    mock_sqs.queue.Queue().get_messages.return_value = msgs
    q = mock_sqs.queue.Queue()
    q_name = "mysqs"
    mock_fire = MagicMock(return_value=True)
    sqs_events._process_queue(q, q_name, mock_fire)
    assert mock_sqs.queue.Queue().get_messages.called, len(msgs)
    assert mock_fire.called, len(msgs)
