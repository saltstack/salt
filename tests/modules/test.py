import unittest
from modules import run_module

class TestModuleTest(unittest.TestCase):
    def test_ping(self):
        ret = run_module('test.ping')
        assert ret == {'return': True}
