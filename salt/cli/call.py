# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
import os

import salt.utils.parsers
from salt.utils.verify import verify_log
from salt.utils.path import expand_glob_path
import salt.cli.caller
import salt.defaults.exitcodes


class SaltCall(salt.utils.parsers.SaltCallOptionParser):
    '''
    Used to locally execute a salt command
    '''

    def run(self):
        '''
        Execute the salt call!
        '''
        self.parse_args()

        if self.options.file_root:
            # check if the argument is pointing to a file on disk
            self.config['file_roots'] = {'base': expand_glob_path(self.options.file_root,
                                                                  self.options.root_dir)}

        if self.options.pillar_root:
            # check if the argument is pointing to a file on disk
            self.config['pillar_roots'] = {'base': expand_glob_path(self.options.pillar_root,
                                                                    self.options.root_dir)}

        if self.options.states_dir:
            # check if the argument is pointing to a file on disk
            states_dir = os.path.abspath(self.options.states_dir)
            self.config['states_dirs'] = [states_dir]

        if self.options.local:
            self.config['file_client'] = 'local'
        if self.options.master:
            self.config['master'] = self.options.master

        # Setup file logging!
        self.setup_logfile_logger()
        verify_log(self.config)

        caller = salt.cli.caller.Caller.factory(self.config)

        if self.options.doc:
            caller.print_docs()
            self.exit(salt.defaults.exitcodes.EX_OK)

        if self.options.grains_run:
            caller.print_grains()
            self.exit(salt.defaults.exitcodes.EX_OK)

        caller.run()
