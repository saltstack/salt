# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import absolute_import

import os

from salt.utils import parsers
from salt.utils.verify import check_user
from salt.exceptions import SaltClientError


class SaltRun(parsers.SaltRunOptionParser):
    '''
    Used to execute Salt runners
    '''

    def run(self):
        '''
        Execute salt-run
        '''
        import salt.runner
        self.parse_args()

        # Setup file logging!
        self.setup_logfile_logger()

        runner = salt.runner.Runner(self.config)
        if self.options.doc:
            runner.print_docs()
            self.exit(os.EX_OK)

        # Run this here so SystemExit isn't raised anywhere else when
        # someone tries to use the runners via the python API
        try:
            if check_user(self.config['user']):
                runner.run()
        except SaltClientError as exc:
            raise SystemExit(str(exc))
