# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.log_test
    ~~~~~~~~~~~~~~~~~~~

    Test salt's "hacked" logging
'''

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath, TestsLoggingHandler

ensure_in_syspath('../')


class TestLog(TestCase):
    '''Test several logging settings'''

    def test_issue_2853_regex_TypeError(self):
        from salt.log import setup as saltlog
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestLog, needs_daemon=False)
