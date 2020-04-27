# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.utils.platform

# Import Salt Testing Libs
from tests.support.case import SSHCase
from tests.support.unit import skipIf


@skipIf(salt.utils.platform.is_windows(), "salt-ssh not available on Windows")
class SSHRawTest(SSHCase):
    """
    testing salt-ssh with raw calls
    """

    def test_ssh_raw(self):
        """
        test salt-ssh with -r argument
        """
        msg = "running raw msg"
        ret = self.run_function("echo {0}".format(msg), raw=True)
        self.assertEqual(ret["stdout"], msg + "\n")
