# Python libs
import logging

import pytest

# Salt libs
from salt.beacons import twilio_txt_msg

# Salt testing libs
from tests.support.mock import MagicMock, patch

try:
    import twilio

    # Grab version, ensure elements are ints
    twilio_version = tuple([int(x) for x in twilio.__version_info__])
    if twilio_version > (5,):
        TWILIO_5 = False
    else:
        TWILIO_5 = True
    HAS_TWILIO = True
except ImportError:
    HAS_TWILIO = False


log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skipif(HAS_TWILIO is False, reason="twilio.rest is not available"),
]


class MockTwilioRestException(Exception):
    """
    Mock TwilioRestException class
    """

    def __init__(self):
        self.code = "error code"
        self.msg = "Exception error"
        self.status = "Not send"
        super().__init__(self.msg)


class MockMessages:
    """
    Mock SMS class
    """

    flag = None

    def __init__(self):
        self.sid = "011"
        self.price = "200"
        self.price_unit = "1"
        self.status = "Sent"
        self.num_segments = "2"
        self.num_media = "0"
        self.body = None
        self.date_sent = "01-01-2015"
        self.date_created = "01-01-2015"
        self.to = None
        self.from_ = None

    def create(self, body, to, from_):
        """
        Mock create method
        """
        msg = MockMessages()
        if self.flag == 1:
            raise MockTwilioRestException()
        msg.body = body
        msg.to = to
        msg.from_ = from_
        return msg

    def list(self, to):
        """
        Mock list method
        """
        msg = MockMessages()
        return [msg]

    def delete(self):
        """
        Mock delete method
        """
        return None


class MockSMS:
    """
    Mock SMS class
    """

    def __init__(self):
        self.messages = MockMessages()


class MockTwilioRestClient:
    """
    Mock TwilioRestClient class
    """

    def __init__(self):
        if TWILIO_5:
            self.sms = MockSMS()
        else:
            self.messages = MockMessages()


@pytest.fixture
def configure_loader_modules():
    return {twilio_txt_msg: {}}


def test_validate_dictionary_config():
    """
    Test empty configuration
    """
    config = {}
    ret = twilio_txt_msg.validate(config)
    assert ret == (False, "Configuration for twilio_txt_msg beacon must be a list.")


def test_validate_empty_config():
    """
    Test empty configuration
    """
    config = [{}]
    ret = twilio_txt_msg.validate(config)
    assert ret == (
        False,
        "Configuration for twilio_txt_msg "
        "beacon must contain account_sid, "
        "auth_token and twilio_number items.",
    )


def test_validate_missing_config_item():
    """
    Test empty configuration
    """
    config = [
        {
            "account_sid": "ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "twilio_number": "+15555555555",
        }
    ]

    ret = twilio_txt_msg.validate(config)
    assert ret == (
        False,
        "Configuration for twilio_txt_msg "
        "beacon must contain account_sid, "
        "auth_token and twilio_number items.",
    )


def test_receive_message():
    """
    Test receive a message
    """
    config = [
        {
            "account_sid": "ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            "auth_token": "my_token",
            "twilio_number": "+15555555555",
        }
    ]

    ret = twilio_txt_msg.validate(config)
    assert ret == (True, "Valid beacon configuration")

    _expected_return = [
        {
            "texts": [
                {
                    "body": "None",
                    "images": [],
                    "from": "None",
                    "id": "011",
                    "sent": "01-01-2015",
                }
            ]
        }
    ]
    mock = MagicMock(return_value=MockTwilioRestClient())
    with patch.object(twilio_txt_msg, "TwilioRestClient", mock):
        ret = twilio_txt_msg.beacon(config)
    assert ret == _expected_return
