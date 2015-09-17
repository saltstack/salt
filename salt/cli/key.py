# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import absolute_import

import os

from salt.utils import parsers
from salt.utils.verify import check_user, verify_env, verify_files, verify_log


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

        if self.config['verify_env']:
            verify_env_dirs = []
            if not self.config['gen_keys']:
                if self.config['transport'] == 'raet':
                    verify_env_dirs.extend([
                        self.config['pki_dir'],
                        os.path.join(self.config['pki_dir'], 'accepted'),
                        os.path.join(self.config['pki_dir'], 'pending'),
                        os.path.join(self.config['pki_dir'], 'rejected'),
                    ])
                elif self.config['transport'] == 'zeromq':
                    verify_env_dirs.extend([
                        self.config['pki_dir'],
                        os.path.join(self.config['pki_dir'], 'minions'),
                        os.path.join(self.config['pki_dir'], 'minions_pre'),
                        os.path.join(self.config['pki_dir'], 'minions_rejected'),
                    ])

            verify_env(
                verify_env_dirs,
                self.config['user'],
                permissive=self.config['permissive_pki_access'],
                pki_dir=self.config['pki_dir'],
            )
            if not self.config['log_file'].startswith(('tcp://',
                                                       'udp://',
                                                       'file://')):
                # Logfile is not using Syslog, verify
                verify_files(
                    [self.config['key_logfile']],
                    self.config['user']
                )

        self.setup_logfile_logger()
        verify_log(self.config)

        key = salt.key.KeyCLI(self.config)
        if check_user(self.config['user']):
            key.run()
