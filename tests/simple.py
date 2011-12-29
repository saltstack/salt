import unittest

class SimpleTest(unittest.TestCase):
    def test_success(self):
        assert True
    @unittest.expectedFailure
    def test_fail(self):
        assert False
