# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
import salt.client.ssh
from salt.utils import parsers


class SaltSSH(parsers.SaltSSHOptionParser):
    '''
    Used to Execute the salt ssh routine
    '''

    def run(self):
        self.parse_args()
        self.setup_logfile_logger()

        ssh = salt.client.ssh.SSH(self.config)
        ssh.run()
