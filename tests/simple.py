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

class SimpleTest(TestCase):
    def test_success(self):
        assert True
    @expectedFailure
    def test_fail(self):
        assert False
