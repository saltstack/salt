# -*- coding: utf-8 -*-
'''
Validate the boto_iam module
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import Salt libs
import integration

# Import 3rd-party libs
NO_BOTO_MODULE = True
BOTO_NOT_CONFIGURED = True
try:
    import boto
    NO_BOTO_MODULE = False
    try:
        boto.connect_iam()
        BOTO_NOT_CONFIGURED = False
    except boto.exception.NoAuthHandlerFound:
        pass
except ImportError:
    pass


@skipIf(
    NO_BOTO_MODULE,
    'Please install the boto library before running boto integration tests.'
)
@skipIf(
    BOTO_NOT_CONFIGURED,
    'Please setup boto AWS credentials before running boto integration tests.'
)
class BotoIAMTest(integration.ModuleCase):

    def test_get_account_id(self):
        ret = self.run_function('boto_iam.get_account_id')
        # The AWS account ID is a 12-digit number.
        # http://docs.aws.amazon.com/general/latest/gr/acct-identifiers.html
        self.assertRegexpMatches(ret, r'^\d{12}$')
