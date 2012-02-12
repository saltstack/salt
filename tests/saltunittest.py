"""
This file provides a single interface to unittest objects for our
tests while supporting python < 2.7 via unittest2.

If you need something from the unittest namespace it should be
imported here from the relevant module and then imported into your
test from here
"""

import sys

# support python < 2.7 via unittest2
if sys.version_info[0:2] < (2,7):
    try:
        from unittest2 import TestLoader, TextTestRunner,\
                              TestCase, expectedFailure, \
                              TestSuite
    except ImportError:
        print "You need to install unittest2 to run the salt tests"
        sys.exit(1)
else:
    from unittest import TestLoader, TextTestRunner,\
                         TestCase, expectedFailure, \
                         TestSuite
