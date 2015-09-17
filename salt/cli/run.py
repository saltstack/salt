# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import absolute_import

from salt.utils import parsers
from salt.utils.verify import check_user, verify_env, verify_files, verify_log
from salt.exceptions import SaltClientError
import salt.defaults.exitcodes  # pylint: disable=W0611


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

        if self.config['verify_env']:
            verify_env([
                    self.config['pki_dir'],
                    self.config['cachedir'],
                ],
                self.config['user'],
                permissive=self.config['permissive_pki_access'],
                pki_dir=self.config['pki_dir'],
            )
            if not self.config['log_file'].startswith(('tcp://',
                                                       'udp://',
                                                       'file://')):
                # Logfile is not using Syslog, verify
                verify_files(
                    [self.config['log_file']],
                    self.config['user']
                )

        # Setup file logging!
        self.setup_logfile_logger()
        verify_log(self.config)

        runner = salt.runner.Runner(self.config)
        if self.options.doc:
            runner.print_docs()
            self.exit(salt.defaults.exitcodes.EX_OK)

        # Run this here so SystemExit isn't raised anywhere else when
        # someone tries to use the runners via the python API
        try:
            if check_user(self.config['user']):
                runner.run()
        except SaltClientError as exc:
            raise SystemExit(str(exc))
