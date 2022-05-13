import pytest
import salt.utils.platform
from tests.support.case import SSHCase
from tests.support.unit import skipIf


@skipIf(salt.utils.platform.is_windows(), "salt-ssh not available on Windows")
class SSHSaltcheckTest(SSHCase):
    """
    testing saltcheck with salt-ssh
    """

    @pytest.mark.slow_test
    def test_saltcheck_run_test(self):
        """
        test saltcheck.run_test with salt-ssh
        """
        saltcheck_test = {
            "module_and_function": "test.echo",
            "assertion": "assertEqual",
            "expected-return": "Test Works",
            "args": ["Test Works"],
        }
        ret = self.run_function("saltcheck.run_test", test=saltcheck_test)
        self.assertDictContainsSubset({"status": "Pass"}, ret)

    @pytest.mark.slow_test
    def test_saltcheck_state(self):
        """
        saltcheck.run_state_tests
        """
        saltcheck_test = "validate-saltcheck"
        ret = self.run_function("saltcheck.run_state_tests", [saltcheck_test])
        self.assertDictContainsSubset(
            {"status": "Pass"}, ret[0]["validate-saltcheck"]["echo_test_hello"]
        )
