import pytest
from tests.support.case import SSHCase


@pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows")
class SSHRawTest(SSHCase):
    """
    testing salt-ssh with raw calls
    """

    @pytest.mark.slow_test
    @pytest.mark.timeout(timeout=60, method="thread")
    def test_ssh_raw(self):
        """
        test salt-ssh with -r argument
        """
        msg = "password: foo"
        ret = self.run_function("echo {}".format(msg), raw=True)
        self.assertEqual(ret["stdout"], msg + "\n")
