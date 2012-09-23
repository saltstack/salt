"""
This file provides a single interface to unittest objects for our
tests while supporting python < 2.7 via unittest2.

If you need something from the unittest namespace it should be
imported here from the relevant module and then imported into your
test from here
"""

# Import python libs
import os
import sys
import logging

# support python < 2.7 via unittest2
if sys.version_info[0:2] < (2, 7):
    try:
        from unittest2 import (
            TestLoader,
            TextTestRunner,
            TestCase,
            expectedFailure,
            TestSuite,
            skipIf
        )
    except ImportError:
        raise SystemExit("You need to install unittest2 to run the salt tests")
else:
    from unittest import (
        TestLoader,
        TextTestRunner,
        TestCase,
        expectedFailure,
        TestSuite,
        skipIf
    )


# Set up paths
TEST_DIR = os.path.dirname(os.path.normpath(os.path.abspath(__file__)))
SALT_LIBS = os.path.dirname(TEST_DIR)

for dir_ in [TEST_DIR, SALT_LIBS]:
    if not dir_ in sys.path:
        sys.path.insert(0, dir_)


class TestsLoggingHandler(object):
    '''
    Simple logging handler which can be used to test if certain logging
    messages get emitted or not::

    ..code-block: python

        with TestsLoggingHandler() as handler:
            # (...)               Do what ever you wish here
            handler.messages    # here are the emitted log messages

    '''
    def __init__(self, level=0, format='%(levelname)s:%(message)s'):
        self.level = level
        self.format = format
        self.activated = False

    def activate(self):
        class Handler(logging.Handler):
            def __init__(self, level):
                logging.Handler.__init__(self, level)
                self.messages = []

            def emit(self, record):
                self.messages.append(self.format(record))

        self.handler = Handler(self.level)
        formatter = logging.Formatter(self.format)
        self.handler.setFormatter(formatter)
        logging.root.addHandler(self.handler)
        self.activated = True

    def deactivate(self):
        if not self.activated:
            return
        logging.root.removeHandler(self.handler)

    @property
    def messages(self):
        if not self.activated:
            return []
        return self.handler.messages

    def clear(self):
        self.handler.messages = []

    def __enter__(self):
        self.activate()
        return self

    def __exit__(self, type, value, traceback):
        self.deactivate()
        self.activated = False
