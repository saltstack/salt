# -*- coding: utf-8 -*-
'''
    tests.unit.log_test
    ~~~~~~~~~~~~~~~~~~~

    Test salt's "hacked" logging

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import logging

# Import salt libs
from salt import log as saltlog
from saltunittest import (
    TestCase, TestLoader, TextTestRunner, TestsLoggingHandler
)


class TestLog(TestCase):
    '''Test several logging settings'''

    def test_issue_2853_regex_TypeError(self):
        from salt import log as saltlog
        # Now, python's logging logger class is ours.
        # Let's make sure we have at least one instance
        log = saltlog.Logging(__name__)

        # Test for a format which includes digits in name formatting.
        log_format = '[%(name)-15s] %(message)s'
        handler = TestsLoggingHandler(format=log_format)
        log.addHandler(handler)

        # Trigger TestsLoggingHandler.__enter__
        with handler:
            # Let's create another log instance to trigger salt's logging class
            # calculations.
            try:
                saltlog.Logging('{0}.with_digits'.format(__name__))
            except Exception, err:
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
                saltlog.Logging('{0}.without_digits'.format(__name__))
            except Exception, err:
                raise AssertionError(
                    'No exception should have been raised: {0}'.format(err)
                )

            # Remove the testing handler
            log.removeHandler(handler)


if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(ConfigTestCase)
    TextTestRunner(verbosity=1).run(tests)
