# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.log_test
    ~~~~~~~~~~~~~~~~~~~

    Test salt's "hacked" logging
'''

# Import python libs
from __future__ import absolute_import
import logging
from salt.ext.six.moves import StringIO

# Import Salt Testing libs
from salttesting.case import TestCase
from salttesting.helpers import ensure_in_syspath, TestsLoggingHandler

ensure_in_syspath('../')

# Import Salt libs
from salt.log import setup as saltlog
from salt.log.handlers import StreamHandler


class TestLog(TestCase):
    '''
    Test several logging settings
    '''

    def test_issue_2853_regex_TypeError(self):
        # Now, python's logging logger class is ours.
        # Let's make sure we have at least one instance
        log = saltlog.SaltLoggingClass(__name__)

        # Test for a format which includes digits in name formatting.
        log_format = '[%(name)-15s] %(message)s'
        handler = TestsLoggingHandler(format=log_format)
        log.addHandler(handler)

        # Trigger TestsLoggingHandler.__enter__
        with handler:
            # Let's create another log instance to trigger salt's logging class
            # calculations.
            try:
                saltlog.SaltLoggingClass('{0}.with_digits'.format(__name__))
            except Exception as err:
                raise AssertionError(
                    'No exception should have been raised: {0}'.format(err)
                )

        # Remove the testing handler
        log.removeHandler(handler)

        # Test for a format which does not include digits in name formatting.
        log_format = '[%(name)s] %(message)s'
        handler = TestsLoggingHandler(format=log_format)
        log.addHandler(handler)

        # Trigger TestsLoggingHandler.__enter__
        with handler:
            # Let's create another log instance to trigger salt's logging class
            # calculations.
            try:
                saltlog.SaltLoggingClass('{0}.without_digits'.format(__name__))
            except Exception as err:
                raise AssertionError(
                    'No exception should have been raised: {0}'.format(err)
                )

            # Remove the testing handler
            log.removeHandler(handler)

    def test_exc_info_on_loglevel(self):
        def raise_exception_on_purpose():
            1/0  # pylint: disable=pointless-statement

        log = saltlog.SaltLoggingClass(__name__)

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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestLog, needs_daemon=False)
