"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import salt.modules.twilio_notify as twilio_notify
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

HAS_LIBS = False
try:
    import twilio

    # Grab version, ensure elements are ints
    twilio_version = tuple([int(x) for x in twilio.__version_info__])
    if twilio_version > (5,):
        TWILIO_5 = False
    else:
        TWILIO_5 = True
    HAS_LIBS = True
except ImportError:
    pass


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


@skipIf(not HAS_LIBS, "twilio.rest is not available")
class TwilioNotifyTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.twilio_notify
    """

    def setup_loader_modules(self):
        return {
            twilio_notify: {
                "TwilioRestClient": MockTwilioRestClient,
                "TwilioRestException": MockTwilioRestException,
            }
        }

    # 'send_sms' function tests: 1

    def test_send_sms(self):
        """
        Test if it send an sms.
        """
        mock = MagicMock(return_value=MockTwilioRestClient())
        with patch.object(twilio_notify, "_get_twilio", mock):
            self.assertDictEqual(
                twilio_notify.send_sms(
                    "twilio-account", "SALTSTACK", "+18019999999", "+18011111111"
                ),
                {
                    "message": {
                        "status": "Sent",
                        "num_segments": "2",
                        "price": "200",
                        "body": "SALTSTACK",
                        "sid": "011",
                        "date_sent": "01-01-2015",
                        "date_created": "01-01-2015",
                        "price_unit": "1",
                    }
                },
            )

            MockMessages.flag = 1
            self.assertDictEqual(
                twilio_notify.send_sms(
                    "twilio-account", "SALTSTACK", "+18019999999", "+18011111111"
                ),
                {
                    "message": {"sid": None},
                    "_error": {
                        "msg": "Exception error",
                        "status": "Not send",
                        "code": "error code",
                    },
                },
            )
