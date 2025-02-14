"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    TestCase for salt.modules.smtp
"""

import pytest

import salt.modules.smtp as smtp
from tests.support.mock import MagicMock, patch


class SMTPRecipientsRefused(Exception):
    """
    Mock SMTPRecipientsRefused class
    """

    def __init__(self, msg):
        super().__init__(msg)
        self.smtp_error = msg


class SMTPHeloError(Exception):
    """
    Mock SMTPHeloError class
    """

    def __init__(self, msg):
        super().__init__(msg)
        self.smtp_error = msg


class SMTPSenderRefused(Exception):
    """
    Mock SMTPSenderRefused class
    """

    def __init__(self, msg):
        super().__init__(msg)
        self.smtp_error = msg


class SMTPDataError(Exception):
    """
    Mock SMTPDataError class
    """

    def __init__(self, msg):
        super().__init__(msg)
        self.smtp_error = msg


class SMTPException(Exception):
    """
    Mock SMTPException class
    """

    def __init__(self, msg):
        super().__init__(msg)
        self.smtp_error = msg


class SMTPAuthenticationError(Exception):
    """
    Mock SMTPAuthenticationError class
    """

    def __init__(self, msg):
        super().__init__(msg)
        self.smtp_error = msg


class MockSMTPSSL:
    """
    Mock SMTP_SSL class
    """

    flag = None

    def __init__(self, server):
        pass

    def sendmail(self, sender, recipient, msg):
        """
        Mock sendmail method
        """
        if self.flag == 1:
            raise SMTPRecipientsRefused("All recipients were refused.")
        elif self.flag == 2:
            raise SMTPHeloError("Helo error")
        elif self.flag == 3:
            raise SMTPSenderRefused("Sender Refused")
        elif self.flag == 4:
            raise SMTPDataError("Data error")
        return (sender, recipient, msg)

    def login(self, username, password):
        """
        Mock login method
        """
        if self.flag == 5:
            raise SMTPAuthenticationError("SMTP Authentication Failure")
        return (username, password)

    @staticmethod
    def quit():
        """
        Mock quit method
        """
        return True


class MockSMTP:
    """
    Mock SMTP class
    """

    flag = None

    def __init__(self, server):
        pass

    @staticmethod
    def ehlo():
        """
        Mock ehlo method
        """
        return True

    @staticmethod
    def has_extn(name):
        """
        Mock has_extn method
        """
        return name

    def starttls(self):
        """
        Mock starttls method
        """
        if self.flag == 1:
            raise SMTPHeloError("Helo error")
        elif self.flag == 2:
            raise SMTPException("Exception error")
        elif self.flag == 3:
            raise RuntimeError
        return True

    def sendmail(self, sender, recipient, msg):
        """
        Mock sendmail method
        """
        if self.flag == 1:
            raise SMTPRecipientsRefused("All recipients were refused.")
        elif self.flag == 2:
            raise SMTPHeloError("Helo error")
        elif self.flag == 3:
            raise SMTPSenderRefused("Sender Refused")
        elif self.flag == 4:
            raise SMTPDataError("Data error")
        return (sender, recipient, msg)

    @staticmethod
    def quit():
        """
        Mock quit method
        """
        return True


class MockGaierror(Exception):
    """
    Mock MockGaierror class
    """

    def __init__(self, msg):
        super().__init__(msg)
        self.smtp_error = msg


class MockSocket:
    """
    Mock Socket class
    """

    def __init__(self):
        self.gaierror = MockGaierror


class MockSmtplib:
    """
    Mock smtplib class
    """

    flag = None

    def __init__(self):
        self.SMTPRecipientsRefused = SMTPRecipientsRefused
        self.SMTPHeloError = SMTPHeloError
        self.SMTPSenderRefused = SMTPSenderRefused
        self.SMTPDataError = SMTPDataError
        self.SMTPException = SMTPException
        self.SMTPAuthenticationError = SMTPAuthenticationError
        self.server = None

    def SMTP_SSL(self, server):
        """
        Mock SMTP_SSL method
        """
        self.server = server
        if self.flag == 1:
            raise MockGaierror("gaierror")
        return MockSMTPSSL("server")

    def SMTP(self, server):
        """
        Mock SMTP method
        """
        self.server = server
        if self.flag == 1:
            raise MockGaierror("gaierror")
        return MockSMTP("server")


@pytest.fixture
def configure_loader_modules():
    return {smtp: {"socket": MockSocket(), "smtplib": MockSmtplib()}}


# 'send_msg' function tests: 1


def test_send_msg():
    """
    Tests if it send a message to an SMTP recipient.
    """
    mock = MagicMock(
        return_value={
            "smtp.server": "",
            "smtp.tls": "True",
            "smtp.sender": "",
            "smtp.username": "",
            "smtp.password": "",
        }
    )
    with patch.dict(smtp.__salt__, {"config.option": mock}):
        assert smtp.send_msg(
            "admin@example.com",
            "This is a salt module test",
            profile="my-smtp-account",
        )

        MockSMTPSSL.flag = 1
        assert not smtp.send_msg(
            "admin@example.com",
            "This is a salt module test",
            profile="my-smtp-account",
        )

        MockSMTPSSL.flag = 2
        assert not smtp.send_msg(
            "admin@example.com",
            "This is a salt module test",
            profile="my-smtp-account",
        )

        MockSMTPSSL.flag = 3
        assert not smtp.send_msg(
            "admin@example.com",
            "This is a salt module test",
            profile="my-smtp-account",
        )

        MockSMTPSSL.flag = 4
        assert not smtp.send_msg(
            "admin@example.com",
            "This is a salt module test",
            profile="my-smtp-account",
        )

    mock = MagicMock(
        return_value={
            "smtp.server": "",
            "smtp.tls": "",
            "smtp.sender": "",
            "smtp.username": "",
            "smtp.password": "",
        }
    )
    with patch.dict(smtp.__salt__, {"config.option": mock}):
        MockSMTPSSL.flag = 5
        assert not smtp.send_msg(
            "admin@example.com",
            "This is a salt module test",
            username="myuser",
            password="verybadpass",
            sender="admin@example.com",
            server="smtp.domain.com",
        )

        MockSMTP.flag = 1
        assert not smtp.send_msg(
            "admin@example.com",
            "This is a salt module test",
            profile="my-smtp-account",
        )

        MockSMTP.flag = 2
        assert not smtp.send_msg(
            "admin@example.com",
            "This is a salt module test",
            profile="my-smtp-account",
        )

        MockSMTP.flag = 3
        assert not smtp.send_msg(
            "admin@example.com",
            "This is a salt module test",
            profile="my-smtp-account",
        )

        MockSmtplib.flag = 1
        assert not smtp.send_msg(
            "admin@example.com",
            "This is a salt module test",
            profile="my-smtp-account",
        )
