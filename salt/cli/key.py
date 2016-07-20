# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import absolute_import

from salt.utils import parsers
from salt.utils.verify import check_user, verify_log


class SaltKey(parsers.SaltKeyOptionParser):
    '''
    Initialize the Salt key manager
    '''

    def run(self):
        '''
        Execute salt-key
        '''
        import salt.key
        self.parse_args()
        multi = False
        if self.config.get('zmq_behavior') and self.config.get('transport') == 'raet':
            multi = True

        self.setup_logfile_logger()
        verify_log(self.config)

        if multi:
            key = salt.key.MultiKeyCLI(self.config)
        else:
            key = salt.key.KeyCLI(self.config)
        if check_user(self.config['user']):
            key.run()
