from modules import run_module
import saltunittest

class TestModuleTest(saltunittest.TestCase):
    def test_ping(self):
        ret = run_module('test.ping')
        assert ret == {'return': True}
