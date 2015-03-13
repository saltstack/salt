# -*- coding: utf-8 -*-
'''
The management of salt command line utilities are stored in here
'''

# Import python libs
from __future__ import print_function
import logging
import os
import sys

# Import salt libs
import salt.cli.caller
import salt.cli.cp
import salt.cli.batch
import salt.client
import salt.client.ssh
import salt.client.netapi
import salt.exitcodes
import salt.output
import salt.runner
import salt.auth
import salt.key

from salt.utils import parsers, print_cli
from salt.utils.verify import check_user, verify_env, verify_files
from salt.exceptions import (
    SaltInvocationError,
    SaltClientError,
    EauthAuthenticationError,
)

log = logging.getLogger(__name__)


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
            # We don't need to bail on config file permission errors
            # if the CLI
            # process is run with the -a flag
            skip_perm_errors = self.options.eauth != ''

            local = salt.client.get_local_client(
                self.get_config_file_path(),
                skip_perm_errors=skip_perm_errors)
        except SaltClientError as exc:
            self.exit(2, '{0}\n'.format(exc))
            return

        if self.options.batch:
            eauth = {}
            if 'token' in self.config:
                eauth['token'] = self.config['token']

            # If using eauth and a token hasn't already been loaded into
            # kwargs, prompt the user to enter auth credentials
            if 'token' not in eauth and self.options.eauth:
                resolver = salt.auth.Resolver(self.config)
                res = resolver.cli(self.options.eauth)
                if self.options.mktoken and res:
                    tok = resolver.token_cli(
                            self.options.eauth,
                            res
                            )
                    if tok:
                        eauth['token'] = tok.get('token', '')
                if not res:
                    sys.exit(2)
                eauth.update(res)
                eauth['eauth'] = self.options.eauth

            if self.options.static:

                batch = salt.cli.batch.Batch(self.config, eauth=eauth, quiet=True)

                ret = {}

                for res in batch.run():
                    ret.update(res)

                self._output_ret(ret, '')

            else:
                batch = salt.cli.batch.Batch(self.config, eauth=eauth)
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
                'show_timeout': self.options.show_timeout,
                'show_jid': self.options.show_jid}

            if 'token' in self.config:
                try:
                    with salt.utils.fopen(os.path.join(self.config['cachedir'], '.root_key'), 'r') as fp_:
                        kwargs['key'] = fp_.readline()
                except IOError:
                    kwargs['token'] = self.config['token']

            if self.selected_target_option:
                kwargs['expr_form'] = self.selected_target_option
            else:
                kwargs['expr_form'] = 'glob'

            if getattr(self.options, 'return'):
                kwargs['ret'] = getattr(self.options, 'return')

            # If using eauth and a token hasn't already been loaded into
            # kwargs, prompt the user to enter auth credentials
            if 'token' not in kwargs and self.options.eauth:
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
                print_cli('Executed command with job ID: {0}'.format(jid))
                return
            retcodes = []
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
                        ret, out, retcode = self._format_ret(full_ret)
                        self._output_ret(ret, out)
                    elif self.config['fun'] == 'sys.doc':
                        ret = {}
                        out = ''
                        for full_ret in local.cmd_cli(**kwargs):
                            ret_, out, retcode = self._format_ret(full_ret)
                            ret.update(ret_)
                        self._output_ret(ret, out)
                    else:
                        if self.options.verbose:
                            kwargs['verbose'] = True
                        ret = {}
                        for full_ret in cmd_func(**kwargs):
                            ret_, out, retcode = self._format_ret(full_ret)
                            retcodes.append(retcode)
                            self._output_ret(ret_, out)
                            ret.update(ret_)

                    # Returns summary
                    if self.config['cli_summary'] is True:
                        if self.config['fun'] != 'sys.doc':
                            if self.options.output is None:
                                self._print_returns_summary(ret)

                    # NOTE: Return code is set here based on if all minions
                    # returned 'ok' with a retcode of 0.
                    # This is the final point before the 'salt' cmd returns,
                    # which is why we set the retcode here.
                    if retcodes.count(0) < len(retcodes):
                        sys.exit(11)

            except (SaltInvocationError, EauthAuthenticationError) as exc:
                ret = str(exc)
                out = ''
                self._output_ret(ret, out)

    def _print_returns_summary(self, ret):
        '''
        Display returns summary
        '''
        return_counter = 0
        not_return_counter = 0
        not_return_minions = []
        for each_minion in ret:
            if ret[each_minion] == "Minion did not return":
                not_return_counter += 1
                not_return_minions.append(each_minion)
            else:
                return_counter += 1
        print_cli('\n')
        print_cli('-------------------------------------------')
        print_cli('Summary')
        print_cli('-------------------------------------------')
        print_cli('# of Minions Targeted: {0}'.format(return_counter + not_return_counter))
        print_cli('# of Minions Returned: {0}'.format(return_counter))
        print_cli('# of Minions Did Not Return: {0}'.format(not_return_counter))
        if self.options.verbose:
            print_cli('Minions Which Did Not Return: {0}'.format(" ".join(not_return_minions)))
        print_cli('-------------------------------------------')

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
        retcode = 0
        for key, data in full_ret.items():
            ret[key] = data['ret']
            if 'out' in data:
                out = data['out']
            if 'retcode' in data:
                retcode = data['retcode']
        return ret, out, retcode

    def _print_docs(self, ret):
        '''
        Print out the docstrings for all of the functions on the minions
        '''
        docs = {}
        if not ret:
            self.exit(2, 'No minions found to gather docs from\n')
        if isinstance(ret, str):
            self.exit(2, '{0}\n'.format(ret))
        for host in ret:
            if ret[host] == 'Minion did not return. [Not connected]':
                continue
            for fun in ret[host]:
                if fun not in docs:
                    if ret[host][fun]:
                        docs[fun] = ret[host][fun]
        for fun in sorted(docs):
            salt.output.display_output(fun + ':', 'text', self.config)
            print_cli(docs[fun])
            print_cli('')


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

        #caller = salt.cli.caller.Caller(self.config)
        caller = salt.cli.caller.Caller.factory(self.config)

        if self.options.doc:
            caller.print_docs()
            self.exit(salt.exitcodes.EX_OK)

        if self.options.grains_run:
            caller.print_grains()
            self.exit(salt.exitcodes.EX_OK)

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
            self.exit(salt.exitcodes.EX_OK)

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


class SaltAPI(parsers.OptionParser, parsers.ConfigDirMixIn,
        parsers.LogLevelMixIn, parsers.PidfileMixin, parsers.DaemonMixIn,
        parsers.MergeConfigMixIn):
    '''
    The cli parser object used to fire up the salt api system.
    '''
    __metaclass__ = parsers.OptionParserMeta

    VERSION = salt.version.__version__

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = '/var/log/salt/api'

    def setup_config(self):
        return salt.config.api_config(self.get_config_file_path())

    def run(self):
        '''
        Run the api
        '''
        self.parse_args()
        try:
            if self.config['verify_env']:
                logfile = self.config['log_file']
                if logfile is not None and not logfile.startswith('tcp://') \
                        and not logfile.startswith('udp://') \
                        and not logfile.startswith('file://'):
                    # Logfile is not using Syslog, verify
                    salt.utils.verify.verify_files(
                        [logfile], self.config['user']
                    )
        except OSError as err:
            log.error(err)
            sys.exit(err.errno)

        self.setup_logfile_logger()
        client = salt.client.netapi.NetapiClient(self.config)
        self.daemonize_if_required()
        self.set_pidfile()
        client.run()
