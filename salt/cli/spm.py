# -*- coding: utf-8 -*-
'''
    salt.cli.spm
    ~~~~~~~~~~~~~

    Salt's spm cli parser.

.. versionadded:: 2015.8.0
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
import salt.spm
import salt.utils.parsers as parsers
from salt.utils.verify import verify_log, verify_env


class SPM(parsers.SPMParser):
    '''
    The cli parser object used to fire up the salt spm system.
    '''

    def run(self):
        '''
        Run the api
        '''
        ui = salt.spm.SPMCmdlineInterface()
        self.parse_args()
        self.setup_logfile_logger()
        v_dirs = [
            self.config['cachedir'],
        ]
        verify_env(v_dirs,
                   self.config['user'],
                   root_dir=self.config['root_dir'],
                   )
        verify_log(self.config)
        client = salt.spm.SPMClient(ui, self.config)
        client.run(self.args)
