# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import absolute_import
import os

from salt.utils import parsers
from salt.config import _expand_glob_path
import salt.cli.caller


class SaltCall(parsers.SaltCallOptionParser):
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
            file_root = os.path.abspath(self.options.file_root)
            self.config['file_roots'] = {'base': _expand_glob_path([file_root])}

        if self.options.pillar_root:
            # check if the argument is pointing to a file on disk
            pillar_root = os.path.abspath(self.options.pillar_root)
            self.config['pillar_roots'] = {'base': _expand_glob_path([pillar_root])}

        if self.options.local:
            self.config['file_client'] = 'local'
        if self.options.master:
            self.config['master'] = self.options.master

        # Setup file logging!
        self.setup_logfile_logger()

        caller = salt.cli.caller.Caller.factory(self.config)

        if self.options.doc:
            caller.print_docs()
            self.exit(os.EX_OK)

        if self.options.grains_run:
            caller.print_grains()
            self.exit(os.EX_OK)

        caller.run()
