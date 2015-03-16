# -*- coding: utf-8 -*-
# Import python libs
from __future__ import print_function
from __future__ import absolute_import
import os
import sys

from salt.utils import parsers, print_cli
from salt.utils.verify import verify_files
from salt.exceptions import (
        SaltClientError,
        SaltInvocationError,
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
        import salt.auth
        import salt.client
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
            import salt.cli.batch
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

            kwargs['delimiter'] = self.options.delimiter

            if self.selected_target_option:
                kwargs['expr_form'] = self.selected_target_option
            else:
                kwargs['expr_form'] = 'glob'

            if getattr(self.options, 'return'):
                kwargs['ret'] = getattr(self.options, 'return')

            if getattr(self.options, 'return_config'):
                kwargs['ret_config'] = getattr(self.options, 'return_config')

            if getattr(self.options, 'metadata'):
                kwargs['metadata'] = getattr(self.options, 'metadata')

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
                errors = []
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
                    if self.options.progress:
                        kwargs['progress'] = True
                        self.config['progress'] = True
                        ret = {}
                        for progress in cmd_func(**kwargs):
                            out = 'progress'
                            self._progress_ret(progress, out)
                            if 'return_count' not in progress:
                                ret.update(progress)
                        self._progress_end(out)
                        self._print_returns_summary(ret)
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
                            try:
                                ret_, out, retcode = self._format_ret(full_ret)
                                retcodes.append(retcode)
                                self._output_ret(ret_, out)
                                ret.update(ret_)
                            except KeyError:
                                errors.append(full_ret)

                    # Returns summary
                    if self.config['cli_summary'] is True:
                        if self.config['fun'] != 'sys.doc':
                            if self.options.output is None:
                                self._print_returns_summary(ret)
                                self._print_errors_summary(errors)

                    # NOTE: Return code is set here based on if all minions
                    # returned 'ok' with a retcode of 0.
                    # This is the final point before the 'salt' cmd returns,
                    # which is why we set the retcode here.
                    if retcodes.count(0) < len(retcodes):
                        sys.exit(11)

            except (SaltInvocationError, EauthAuthenticationError, SaltClientError) as exc:
                ret = str(exc)
                out = ''
                self._output_ret(ret, out)

    def _print_errors_summary(self, errors):
        if errors:
            print_cli('\n')
            print_cli('---------------------------')
            print_cli('Errors')
            print_cli('---------------------------')
            for minion in errors:
                print_cli(self._format_error(minion))

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

    def _progress_end(self, out):
        import salt.output
        salt.output.progress_end(self.progress_bar)

    def _progress_ret(self, progress, out):
        '''
        Print progress events
        '''
        import salt.output
        # Get the progress bar
        if not hasattr(self, 'progress_bar'):
            self.progress_bar = salt.output.get_progress(self.config, out, progress)
        salt.output.update_progress(self.config, progress, self.progress_bar, out)

    def _output_ret(self, ret, out):
        '''
        Print the output from a single return to the terminal
        '''
        import salt.output
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

    def _format_error(self, minion_error):
        for minion, error_doc in minion_error.items():
            error = 'Minion [{0}] encountered exception \'{1}\''.format(minion, error_doc['message'])
        return error

    def _print_docs(self, ret):
        '''
        Print out the docstrings for all of the functions on the minions
        '''
        import salt.output
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
