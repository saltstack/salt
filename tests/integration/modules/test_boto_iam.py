# -*- coding: utf-8 -*-
"""
Validate the boto_iam module
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.unit import skipIf

# Import 3rd-party libs
try:
    import boto

    NO_BOTO_MODULE = False
except ImportError:
    NO_BOTO_MODULE = True


@skipIf(
    NO_BOTO_MODULE,
    "Please install the boto library before running boto integration tests.",
)
class BotoIAMTest(ModuleCase):
    def setUp(self):
        try:
            boto.connect_iam()
        except boto.exception.NoAuthHandlerFound:
            self.skipTest(
                "Please setup boto AWS credentials before running boto integration tests."
            )

    def test_get_account_id(self):
        ret = self.run_function("boto_iam.get_account_id")
        # The AWS account ID is a 12-digit number.
        # http://docs.aws.amazon.com/general/latest/gr/acct-identifiers.html
        self.assertRegex(ret, r"^\d{12}$")
