from modules import run_module
import sys

# support python < 2.7 via unittest2
if sys.version_info[0:2] < (2,7):
    try:
        from unittest2 import TestCase, expectedFailure
    except ImportError:
        print "You need to install unittest2 to run the salt tests"
        sys.exit(1)
else:
    from unittest import TestCase, expectedFailure

class TestModuleTest(TestCase):
    def test_ping(self):
        ret = run_module('test.ping')
        assert ret == {'return': True}
