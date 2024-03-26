"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    tests.unit.log_test
    ~~~~~~~~~~~~~~~~~~~

    Test salt's "hacked" logging
"""

import io
import logging

from salt._logging.handlers import StreamHandler
from salt._logging.impl import SaltLoggingClass
from tests.support.helpers import TstSuiteLoggingHandler


def test_issue_2853_regex_TypeError():
    # Now, python's logging logger class is ours.
    # Let's make sure we have at least one instance
    log = SaltLoggingClass(__name__)

    # Test for a format which includes digits in name formatting.
    log_format = "[%(name)-15s] %(message)s"
    handler = TstSuiteLoggingHandler(format=log_format)
    log.addHandler(handler)

    # Trigger TstSuiteLoggingHandler.__enter__
    with handler:
        # Let's create another log instance to trigger salt's logging class
        # calculations.
        try:
            SaltLoggingClass(f"{__name__}.with_digits")
        except Exception as err:  # pylint: disable=broad-except
            raise AssertionError(f"No exception should have been raised: {err}")

    # Remove the testing handler
    log.removeHandler(handler)

    # Test for a format which does not include digits in name formatting.
    log_format = "[%(name)s] %(message)s"
    handler = TstSuiteLoggingHandler(format=log_format)
    log.addHandler(handler)

    # Trigger TstSuiteLoggingHandler.__enter__
    with handler:
        # Let's create another log instance to trigger salt's logging class
        # calculations.
        try:
            SaltLoggingClass(f"{__name__}.without_digits")
        except Exception as err:  # pylint: disable=broad-except
            raise AssertionError(f"No exception should have been raised: {err}")

        # Remove the testing handler
        log.removeHandler(handler)


def test_exc_info_on_loglevel():
    def raise_exception_on_purpose():
        1 / 0  # pylint: disable=pointless-statement

    log = SaltLoggingClass(__name__)

    # Only stream2 should contain the traceback
    stream1 = io.StringIO()
    stream2 = io.StringIO()
    handler1 = StreamHandler(stream1)
    handler2 = StreamHandler(stream2)

    handler1.setLevel(logging.INFO)
    handler2.setLevel(logging.DEBUG)

    log.addHandler(handler1)
    log.addHandler(handler2)

    try:
        raise_exception_on_purpose()
    except ZeroDivisionError as exc:
        log.error(
            "Exception raised on purpose caught: ZeroDivisionError",
            exc_info_on_loglevel=logging.DEBUG,
        )

    try:
        assert (
            "Exception raised on purpose caught: ZeroDivisionError"
            in stream1.getvalue()
        )
        assert "Traceback (most recent call last)" not in stream1.getvalue()
        assert (
            "Exception raised on purpose caught: ZeroDivisionError"
            in stream2.getvalue()
        )
        assert "Traceback (most recent call last)" in stream2.getvalue()
    finally:
        log.removeHandler(handler1)
        log.removeHandler(handler2)

    # Both streams should contain the traceback
    stream1 = io.StringIO()
    stream2 = io.StringIO()
    handler1 = StreamHandler(stream1)
    handler2 = StreamHandler(stream2)

    handler1.setLevel(logging.INFO)
    handler2.setLevel(logging.DEBUG)

    log.addHandler(handler1)
    log.addHandler(handler2)

    try:
        raise_exception_on_purpose()
    except ZeroDivisionError as exc:
        log.error(
            "Exception raised on purpose caught: ZeroDivisionError",
            exc_info_on_loglevel=logging.INFO,
        )

    try:
        assert (
            "Exception raised on purpose caught: ZeroDivisionError"
            in stream1.getvalue()
        )
        assert "Traceback (most recent call last)" in stream1.getvalue()
        assert (
            "Exception raised on purpose caught: ZeroDivisionError"
            in stream2.getvalue()
        )
        assert "Traceback (most recent call last)" in stream2.getvalue()
    finally:
        log.removeHandler(handler1)
        log.removeHandler(handler2)

    # No streams should contain the traceback
    stream1 = io.StringIO()
    stream2 = io.StringIO()
    handler1 = StreamHandler(stream1)
    handler2 = StreamHandler(stream2)

    handler1.setLevel(logging.ERROR)
    handler2.setLevel(logging.INFO)

    log.addHandler(handler1)
    log.addHandler(handler2)

    try:
        raise_exception_on_purpose()
    except ZeroDivisionError as exc:
        log.error(
            "Exception raised on purpose caught: ZeroDivisionError",
            exc_info_on_loglevel=logging.DEBUG,
        )

    try:
        assert (
            "Exception raised on purpose caught: ZeroDivisionError"
            in stream1.getvalue()
        )
        assert "Traceback (most recent call last)" not in stream1.getvalue()
        assert (
            "Exception raised on purpose caught: ZeroDivisionError"
            in stream2.getvalue()
        )
        assert "Traceback (most recent call last)" not in stream2.getvalue()
    finally:
        log.removeHandler(handler1)
        log.removeHandler(handler2)
