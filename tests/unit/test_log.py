# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.unit.log_test
    ~~~~~~~~~~~~~~~~~~~

    Test salt's "hacked" logging
'''

# Import python libs
from __future__ import absolute_import
import logging
from salt.ext.six.moves import StringIO

# Import Salt Testing libs
from tests.support.case import TestCase
from tests.support.helpers import TstSuiteLoggingHandler

# Import Salt libs
from salt._logging.impl import SaltLoggingClass
from salt._logging.handlers import StreamHandler


class TestLog(TestCase):
    '''
    Test several logging settings
    '''

    def test_issue_2853_regex_TypeError(self):
        # Now, python's logging logger class is ours.
        # Let's make sure we have at least one instance
        log = SaltLoggingClass(__name__)

        # Test for a format which includes digits in name formatting.
        log_format = '[%(name)-15s] %(message)s'
        handler = TstSuiteLoggingHandler(format=log_format)
        log.addHandler(handler)

        # Trigger TstSuiteLoggingHandler.__enter__
        with handler:
            # Let's create another log instance to trigger salt's logging class
            # calculations.
            try:
                SaltLoggingClass('{0}.with_digits'.format(__name__))
            except Exception as err:
                raise AssertionError(
                    'No exception should have been raised: {0}'.format(err)
                )

        # Remove the testing handler
        log.removeHandler(handler)

        # Test for a format which does not include digits in name formatting.
        log_format = '[%(name)s] %(message)s'
        handler = TstSuiteLoggingHandler(format=log_format)
        log.addHandler(handler)

        # Trigger TstSuiteLoggingHandler.__enter__
        with handler:
            # Let's create another log instance to trigger salt's logging class
            # calculations.
            try:
                SaltLoggingClass('{0}.without_digits'.format(__name__))
            except Exception as err:
                raise AssertionError(
                    'No exception should have been raised: {0}'.format(err)
                )

            # Remove the testing handler
            log.removeHandler(handler)

    def test_exc_info_on_loglevel(self):
        def raise_exception_on_purpose():
            1/0  # pylint: disable=pointless-statement

        log = SaltLoggingClass(__name__)

        # Only stream2 should contain the traceback
        stream1 = StringIO()
        stream2 = StringIO()
        handler1 = StreamHandler(stream1)
        handler2 = StreamHandler(stream2)

        handler1.setLevel(logging.INFO)
        handler2.setLevel(logging.DEBUG)

        log.addHandler(handler1)
        log.addHandler(handler2)

        try:
            raise_exception_on_purpose()
        except ZeroDivisionError as exc:
            log.error('Exception raised on purpose caught: ZeroDivisionError',
                      exc_info_on_loglevel=logging.DEBUG)

        try:
            self.assertIn(
                'Exception raised on purpose caught: ZeroDivisionError',
                stream1.getvalue()
            )
            self.assertNotIn('Traceback (most recent call last)', stream1.getvalue())
            self.assertIn(
                'Exception raised on purpose caught: ZeroDivisionError',
                stream2.getvalue()
            )
            self.assertIn('Traceback (most recent call last)', stream2.getvalue())
        finally:
            log.removeHandler(handler1)
            log.removeHandler(handler2)

        # Both streams should contain the traceback
        stream1 = StringIO()
        stream2 = StringIO()
        handler1 = StreamHandler(stream1)
        handler2 = StreamHandler(stream2)

        handler1.setLevel(logging.INFO)
        handler2.setLevel(logging.DEBUG)

        log.addHandler(handler1)
        log.addHandler(handler2)

        try:
            raise_exception_on_purpose()
        except ZeroDivisionError as exc:
            log.error('Exception raised on purpose caught: ZeroDivisionError',
                      exc_info_on_loglevel=logging.INFO)

        try:
            self.assertIn(
                'Exception raised on purpose caught: ZeroDivisionError',
                stream1.getvalue()
            )
            self.assertIn('Traceback (most recent call last)', stream1.getvalue())
            self.assertIn(
                'Exception raised on purpose caught: ZeroDivisionError',
                stream2.getvalue()
            )
            self.assertIn('Traceback (most recent call last)', stream2.getvalue())
        finally:
            log.removeHandler(handler1)
            log.removeHandler(handler2)

        # No streams should contain the traceback
        stream1 = StringIO()
        stream2 = StringIO()
        handler1 = StreamHandler(stream1)
        handler2 = StreamHandler(stream2)

        handler1.setLevel(logging.ERROR)
        handler2.setLevel(logging.INFO)

        log.addHandler(handler1)
        log.addHandler(handler2)

        try:
            raise_exception_on_purpose()
        except ZeroDivisionError as exc:
            log.error('Exception raised on purpose caught: ZeroDivisionError',
                      exc_info_on_loglevel=logging.DEBUG)

        try:
            self.assertIn(
                'Exception raised on purpose caught: ZeroDivisionError',
                stream1.getvalue()
            )
            self.assertNotIn('Traceback (most recent call last)', stream1.getvalue())
            self.assertIn(
                'Exception raised on purpose caught: ZeroDivisionError',
                stream2.getvalue()
            )
            self.assertNotIn('Traceback (most recent call last)', stream2.getvalue())
        finally:
            log.removeHandler(handler1)
            log.removeHandler(handler2)
