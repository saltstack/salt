# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import sys

import salt.client.ssh
import salt.utils.parsers
from salt.utils.verify import verify_log


class SaltSSH(salt.utils.parsers.SaltSSHOptionParser):
    """
    Used to Execute the salt ssh routine
    """

    def run(self):
        if "-H" in sys.argv or "--hosts" in sys.argv:
            sys.argv += ["x", "x"]  # Hack: pass a mandatory two options
            # that won't be used anyways with -H or --hosts
        self.parse_args()
        self.setup_logfile_logger()
        verify_log(self.config)

        ssh = salt.client.ssh.SSH(self.config)
        ssh.run()
