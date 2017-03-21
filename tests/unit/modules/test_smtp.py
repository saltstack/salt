# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.smtp as smtp

smtp.__salt__ = {}


class SMTPRecipientsRefused(Exception):
    '''
    Mock SMTPRecipientsRefused class
    '''
    def __init__(self, msg):
        super(SMTPRecipientsRefused, self).__init__(msg)
        self.smtp_error = msg


class SMTPHeloError(Exception):
    '''
    Mock SMTPHeloError class
    '''
    def __init__(self, msg):
        super(SMTPHeloError, self).__init__(msg)
        self.smtp_error = msg


class SMTPSenderRefused(Exception):
    '''
    Mock SMTPSenderRefused class
    '''
    def __init__(self, msg):
        super(SMTPSenderRefused, self).__init__(msg)
        self.smtp_error = msg


class SMTPDataError(Exception):
    '''
    Mock SMTPDataError class
    '''
    def __init__(self, msg):
        super(SMTPDataError, self).__init__(msg)
        self.smtp_error = msg


class SMTPException(Exception):
    '''
    Mock SMTPException class
    '''
    def __init__(self, msg):
        super(SMTPException, self).__init__(msg)
        self.smtp_error = msg


class SMTPAuthenticationError(Exception):
    '''
    Mock SMTPAuthenticationError class
    '''
    def __init__(self, msg):
        super(SMTPAuthenticationError, self).__init__(msg)
        self.smtp_error = msg


class MockSMTPSSL(object):
    '''
    Mock SMTP_SSL class
    '''
    flag = None

    def __init__(self, server):
        pass

    def sendmail(self, sender, recipient, msg):
        '''
        Mock sendmail method
        '''
        if self.flag == 1:
            raise SMTPRecipientsRefused('All recipients were refused.')
        elif self.flag == 2:
            raise SMTPHeloError('Helo error')
        elif self.flag == 3:
            raise SMTPSenderRefused('Sender Refused')
        elif self.flag == 4:
            raise SMTPDataError('Data error')
        return (sender, recipient, msg)

    def login(self, username, password):
        '''
        Mock login method
        '''
        if self.flag == 5:
            raise SMTPAuthenticationError('SMTP Authentication Failure')
        return (username, password)

    @staticmethod
    def quit():
        '''
        Mock quit method
        '''
        return True


class MockSMTP(object):
    '''
    Mock SMTP class
    '''
    flag = None

    def __init__(self, server):
        pass

    @staticmethod
    def ehlo():
        '''
        Mock ehlo method
        '''
        return True

    @staticmethod
    def has_extn(name):
        '''
        Mock has_extn method
        '''
        return name

    def starttls(self):
        '''
        Mock starttls method
        '''
        if self.flag == 1:
            raise SMTPHeloError('Helo error')
        elif self.flag == 2:
            raise SMTPException('Exception error')
        elif self.flag == 3:
            raise RuntimeError
        return True

    def sendmail(self, sender, recipient, msg):
        '''
        Mock sendmail method
        '''
        if self.flag == 1:
            raise SMTPRecipientsRefused('All recipients were refused.')
        elif self.flag == 2:
            raise SMTPHeloError('Helo error')
        elif self.flag == 3:
            raise SMTPSenderRefused('Sender Refused')
        elif self.flag == 4:
            raise SMTPDataError('Data error')
        return (sender, recipient, msg)

    @staticmethod
    def quit():
        '''
        Mock quit method
        '''
        return True


class MockGaierror(Exception):
    '''
    Mock MockGaierror class
    '''
    def __init__(self, msg):
        super(MockGaierror, self).__init__(msg)
        self.smtp_error = msg


class MockSocket(object):
    '''
    Mock Socket class
    '''
    def __init__(self):
        self.gaierror = MockGaierror


class MockSmtplib(object):
    '''
    Mock smtplib class
    '''
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
        '''
        Mock SMTP_SSL method
        '''
        self.server = server
        if self.flag == 1:
            raise MockGaierror('gaierror')
        return MockSMTPSSL('server')

    def SMTP(self, server):
        '''
        Mock SMTP method
        '''
        self.server = server
        if self.flag == 1:
            raise MockGaierror('gaierror')
        return MockSMTP('server')

smtp.smtplib = MockSmtplib()
smtp.socket = MockSocket()


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SmtpTestCase(TestCase):
    '''
    TestCase for salt.modules.smtp
    '''
    # 'send_msg' function tests: 1

    def test_send_msg(self):
        '''
        Tests if it send a message to an SMTP recipient.
        '''
        mock = MagicMock(return_value={'smtp.server': '', 'smtp.tls': 'True',
                                       'smtp.sender': '', 'smtp.username': '',
                                       'smtp.password': ''})
        with patch.dict(smtp.__salt__, {'config.option': mock}):
            self.assertTrue(smtp.send_msg('admin@example.com',
                                          'This is a salt module test',
                                          profile='my-smtp-account'))

            MockSMTPSSL.flag = 1
            self.assertFalse(smtp.send_msg('admin@example.com',
                                           'This is a salt module test',
                                           profile='my-smtp-account'))

            MockSMTPSSL.flag = 2
            self.assertFalse(smtp.send_msg('admin@example.com',
                                           'This is a salt module test',
                                           profile='my-smtp-account'))

            MockSMTPSSL.flag = 3
            self.assertFalse(smtp.send_msg('admin@example.com',
                                           'This is a salt module test',
                                           profile='my-smtp-account'))

            MockSMTPSSL.flag = 4
            self.assertFalse(smtp.send_msg('admin@example.com',
                                           'This is a salt module test',
                                           profile='my-smtp-account'))

        mock = MagicMock(return_value={'smtp.server': '', 'smtp.tls': '',
                                       'smtp.sender': '', 'smtp.username': '',
                                       'smtp.password': ''})
        with patch.dict(smtp.__salt__, {'config.option': mock}):
            MockSMTPSSL.flag = 5
            self.assertFalse(smtp.send_msg('admin@example.com',
                                           'This is a salt module test',
                                           username='myuser',
                                           password='verybadpass',
                                           sender='admin@example.com',
                                           server='smtp.domain.com'))

            MockSMTP.flag = 1
            self.assertFalse(smtp.send_msg('admin@example.com',
                                           'This is a salt module test',
                                           profile='my-smtp-account'))

            MockSMTP.flag = 2
            self.assertFalse(smtp.send_msg('admin@example.com',
                                           'This is a salt module test',
                                           profile='my-smtp-account'))

            MockSMTP.flag = 3
            self.assertFalse(smtp.send_msg('admin@example.com',
                                           'This is a salt module test',
                                           profile='my-smtp-account'))

            MockSmtplib.flag = 1
            self.assertFalse(smtp.send_msg('admin@example.com',
                                           'This is a salt module test',
                                           profile='my-smtp-account'))
