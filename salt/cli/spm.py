# -*- coding: utf-8 -*-
'''
    salt.cli.spm
    ~~~~~~~~~~~~~

    Salt's spm cli parser.

.. versionadded:: 2015.8.0
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt libs
import salt.client.spm
import salt.utils.parsers as parsers


class SPM(parsers.SPMParser):
    '''
    The cli parser object used to fire up the salt spm system.
    '''

    def run(self):
        '''
        Run the api
        '''
        self.parse_args()
        self.setup_logfile_logger()
        client = salt.client.spm.SPMClient(self.config)
        client.run(self.args)
