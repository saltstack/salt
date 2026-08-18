"""
Validate the boto_iam module
"""

import pytest

from tests.support.case import ModuleCase

try:
    import boto

    NO_BOTO_MODULE = False
except ImportError:
    NO_BOTO_MODULE = True


@pytest.mark.skipif(
    NO_BOTO_MODULE,
    reason="Please install the boto library before running boto integration tests.",
)
class BotoIAMTest(ModuleCase):
    def setUp(self):
        try:
            boto.connect_iam()
        except boto.exception.NoAuthHandlerFound:
            self.skipTest(
                "Please setup boto AWS credentials before running boto integration"
                " tests."
            )

    def test_get_account_id(self):
        ret = self.run_function("boto_iam.get_account_id")
        # The AWS account ID is a 12-digit number.
        # http://docs.aws.amazon.com/general/latest/gr/acct-identifiers.html
        self.assertRegex(ret, r"^\d{12}$")
