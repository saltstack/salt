# -*- coding: utf-8 -*-
'''
    salt.cli.api
    ~~~~~~~~~~~~~

    Salt's api cli parser.

'''

# Import Python libs
from __future__ import absolute_import, print_function
import logging

# Import Salt libs
import salt.client.netapi
import salt.utils.parsers as parsers
from salt.utils.verify import verify_log


log = logging.getLogger(__name__)


class SaltAPI(parsers.SaltAPIParser):
    '''
    The cli parser object used to fire up the salt api system.
    '''
    def run(self):
        '''
        Run the api
        '''
        self.parse_args()
        self.setup_logfile_logger()
        verify_log(self.config)
        self.daemonize_if_required()
        client = salt.client.netapi.NetapiClient(self.config)
        self.set_pidfile()
        client.run()
