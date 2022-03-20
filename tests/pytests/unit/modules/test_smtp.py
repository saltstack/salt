import pytest
import salt.modules.smtp as smtp
from tests.support.mock import MagicMock, patch

@pytest.fixture
def configure_loader_modules():
    return {smtp: {
        "HAS_LIBS": True
    }}

def test_send_msg_html():
    """
    Test to send a message via SMTP Module with is_html=True
    """
    name = "SMTP Module for saltstac"

    comt = "Need to send message to admin@example.com: This is a salt module"

    ret = True
    mock = MagicMock(return_value={
        "ehlo": MagicMock(return_value=True),
        "has_extn": MagicMock(return_value=False),
        "sendmail": MagicMock(return_value=True)
    })

    with patch.dict(smtp.smtplib.SMTP_SSL, mock):
        assert ret == smtp.send_msg(
            recipient="recipient@gmail.com",
            sender="admin@example.com",
            subject="Message from Salt",
            is_html=True
        )