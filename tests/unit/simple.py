from saltunittest import TestCase, expectedFailure


class SimpleTest(TestCase):
    def test_success(self):
        assert True

    @expectedFailure
    def test_fail(self):
        assert False
