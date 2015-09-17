# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
import salt.client.ssh
from salt.utils import parsers
from salt.utils.verify import verify_log


class SaltSSH(parsers.SaltSSHOptionParser):
    '''
    Used to Execute the salt ssh routine
    '''

    def run(self):
        self.parse_args()
        self.setup_logfile_logger()
        verify_log(self.config)

        ssh = salt.client.ssh.SSH(self.config)
        ssh.run()
