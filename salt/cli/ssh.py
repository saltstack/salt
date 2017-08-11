# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
import salt.client.ssh
import salt.utils.parsers
from salt.utils.verify import verify_log


class SaltSSH(salt.utils.parsers.SaltSSHOptionParser):
    '''
    Used to Execute the salt ssh routine
    '''

    def run(self):
        self.parse_args()
        self.setup_logfile_logger()
        verify_log(self.config)

        ssh = salt.client.ssh.SSH(self.config)
        ssh.run()
