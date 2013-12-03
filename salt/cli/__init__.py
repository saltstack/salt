# -*- coding: utf-8 -*-
'''
The management of salt command line utilities are stored in here
'''

# Import python libs
import os
import sys

# Import salt libs
import salt.cli.caller
import salt.cli.cp
import salt.cli.batch
import salt.client
import salt.client.ssh
import salt.output
import salt.runner
import salt.auth
import salt.key

from salt.utils import parsers
from salt.utils.verify import check_user, verify_env, verify_files
from salt.exceptions import (
    SaltInvocationError,
    SaltClientError,
    EauthAuthenticationError
)


class SaltCMD(parsers.SaltCMDOptionParser):
    '''
    The execution of a salt command happens here
    '''

    def run(self):
        '''
        Execute the salt command line
        '''
        self.parse_args()

        if self.config['verify_env']:
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

        try:
            local = salt.client.LocalClient(self.get_config_file_path())
        except SaltClientError as exc:
            self.exit(2, '{0}\n'.format(exc))
            return

        if self.options.batch:
            batch = salt.cli.batch.Batch(self.config)
            # Printing the output is already taken care of in run() itself
            for res in batch.run():
                pass
        else:
            if self.options.timeout <= 0:
                self.options.timeout = local.opts['timeout']

            kwargs = {
                'tgt': self.config['tgt'],
                'fun': self.config['fun'],
                'arg': self.config['arg'],
                'timeout': self.options.timeout,
                'show_timeout': self.options.show_timeout}

            if 'token' in self.config:
                kwargs['token'] = self.config['token']

            if self.selected_target_option:
                kwargs['expr_form'] = self.selected_target_option
            else:
                kwargs['expr_form'] = 'glob'

            if getattr(self.options, 'return'):
                kwargs['ret'] = getattr(self.options, 'return')

            # If using eauth and a token hasn't already been loaded into
            # kwargs, prompt the user to enter auth credentials
            if not 'token' in kwargs and self.options.eauth:
                resolver = salt.auth.Resolver(self.config)
                res = resolver.cli(self.options.eauth)
                if self.options.mktoken and res:
                    tok = resolver.token_cli(
                            self.options.eauth,
                            res
                            )
                    if tok:
                        kwargs['token'] = tok.get('token', '')
                if not res:
                    sys.exit(2)
                kwargs.update(res)
                kwargs['eauth'] = self.options.eauth

            if self.config['async']:
                jid = local.cmd_async(**kwargs)
                print('Executed command with job ID: {0}'.format(jid))
                return
            try:
                # local will be None when there was an error
                if local:
                    if self.options.subset:
                        cmd_func = local.cmd_subset
                        kwargs['sub'] = self.options.subset
                        kwargs['cli'] = True
                    else:
                        cmd_func = local.cmd_cli
                    if self.options.static:
                        if self.options.verbose:
                            kwargs['verbose'] = True
                        full_ret = local.cmd_full_return(**kwargs)
                        ret, out = self._format_ret(full_ret)
                        self._output_ret(ret, out)
                    elif self.config['fun'] == 'sys.doc':
                        ret = {}
                        out = ''
                        for full_ret in local.cmd_cli(**kwargs):
                            ret_, out = self._format_ret(full_ret)
                            ret.update(ret_)
                        self._output_ret(ret, out)
                    else:
                        if self.options.verbose:
                            kwargs['verbose'] = True
                        for full_ret in cmd_func(**kwargs):
                            ret, out = self._format_ret(full_ret)
                            self._output_ret(ret, out)
            except (SaltInvocationError, EauthAuthenticationError) as exc:
                ret = str(exc)
                out = ''
                self._output_ret(ret, out)

    def _output_ret(self, ret, out):
        '''
        Print the output from a single return to the terminal
        '''
        # Handle special case commands
        if self.config['fun'] == 'sys.doc' and not isinstance(ret, Exception):
            self._print_docs(ret)
        else:
            # Determine the proper output method and run it
            salt.output.display_output(ret, out, self.config)
        if not ret:
            sys.exit(2)

    def _format_ret(self, full_ret):
        '''
        Take the full return data and format it to simple output
        '''
        ret = {}
        out = ''
        for key, data in full_ret.items():
            ret[key] = data['ret']
            if 'out' in data:
                out = data['out']
        return ret, out

    def _print_docs(self, ret):
        '''
        Print out the docstrings for all of the functions on the minions
        '''
        docs = {}
        if not ret:
            self.exit(2, 'No minions found to gather docs from\n')

        for host in ret:
            for fun in ret[host]:
                if fun not in docs:
                    if ret[host][fun]:
                        docs[fun] = ret[host][fun]
        for fun in sorted(docs):
            salt.output.display_output(fun + ':', 'text', self.config)
            print(docs[fun])
            print('')


class SaltCP(parsers.SaltCPOptionParser):
    '''
    Run the salt-cp command line client
    '''

    def run(self):
        '''
        Execute salt-cp
        '''
        self.parse_args()

        if self.config['verify_env']:
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

        cp_ = salt.cli.cp.SaltCP(self.config)
        cp_.run()


class SaltKey(parsers.SaltKeyOptionParser):
    '''
    Initialize the Salt key manager
    '''

    def run(self):
        '''
        Execute salt-key
        '''
        self.parse_args()

        if self.config['verify_env']:
            verify_env_dirs = []
            if not self.config['gen_keys']:
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

        key = salt.key.KeyCLI(self.config)
        if check_user(self.config['user']):
            key.run()


class SaltCall(parsers.SaltCallOptionParser):
    '''
    Used to locally execute a salt command
    '''

    def run(self):
        '''
        Execute the salt call!
        '''
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

        if self.options.file_root:
            # check if the argument is pointing to a file on disk
            file_root = os.path.abspath(self.options.file_root)
            self.config['file_roots'] = {'base': [file_root]}

        if self.options.pillar_root:
            # check if the argument is pointing to a file on disk
            pillar_root = os.path.abspath(self.options.pillar_root)
            self.config['pillar_roots'] = {'base': [pillar_root]}

        if self.options.local:
            self.config['file_client'] = 'local'
        if self.options.master:
            self.config['master'] = self.options.master

        # Setup file logging!
        self.setup_logfile_logger()

        caller = salt.cli.caller.Caller(self.config)

        if self.options.doc:
            caller.print_docs()
            self.exit(0)

        if self.options.grains_run:
            caller.print_grains()
            self.exit(0)

        caller.run()


class SaltRun(parsers.SaltRunOptionParser):
    '''
    Used to execute Salt runners
    '''
    def run(self):
        '''
        Execute salt-run
        '''
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

        runner = salt.runner.Runner(self.config)
        if self.options.doc:
            runner._print_docs()
            self.exit(0)

        # Run this here so SystemExit isn't raised anywhere else when
        # someone tries to use the runners via the python API
        try:
            if check_user(self.config['user']):
                runner.run()
        except SaltClientError as exc:
            raise SystemExit(str(exc))


class SaltSSH(parsers.SaltSSHOptionParser):
    '''
    Used to Execute the salt ssh routine
    '''
    def run(self):
        self.parse_args()

        ssh = salt.client.ssh.SSH(self.config)
        ssh.run()
