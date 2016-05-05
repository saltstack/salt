# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function
import os
import sys

# Import Salt libs
import salt.utils.job
from salt.ext.six import string_types
from salt.utils import parsers, print_cli
from salt.utils.verify import verify_log
from salt.exceptions import (
        SaltClientError,
        SaltInvocationError,
        EauthAuthenticationError
        )

# Import 3rd-party libs
import salt.ext.six as six


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

        # Setup file logging!
        self.setup_logfile_logger()
        verify_log(self.config)

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

        if self.options.batch or self.options.static:
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
                    sys.stderr.write('ERROR: Authentication failed\n')
                    sys.exit(2)
                eauth.update(res)
                eauth['eauth'] = self.options.eauth

            if self.options.static:

                if not self.options.batch:
                    self.config['batch'] = '100%'

                batch = salt.cli.batch.Batch(self.config, eauth=eauth, quiet=True)

                ret = {}

                for res in batch.run():
                    ret.update(res)

                self._output_ret(ret, '')

            else:
                try:
                    batch = salt.cli.batch.Batch(self.config, eauth=eauth, parser=self.options)
                except salt.exceptions.SaltClientError as exc:
                    # We will print errors to the console further down the stack
                    sys.exit(1)
                # Printing the output is already taken care of in run() itself
                for res in batch.run():
                    if self.options.failhard:
                        for ret in six.itervalues(res):
                            retcode = salt.utils.job.get_retcode(ret)
                            if retcode != 0:
                                sys.stderr.write(
                                    '{0}\nERROR: Minions returned with non-zero exit code.\n'.format(
                                        res
                                    )
                                )
                                sys.exit(retcode)

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
                    sys.stderr.write('ERROR: Authentication failed\n')
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

                    if self.options.progress:
                        kwargs['progress'] = True
                        self.config['progress'] = True
                        ret = {}
                        for progress in cmd_func(**kwargs):
                            out = 'progress'
                            try:
                                self._progress_ret(progress, out)
                            except salt.exceptions.LoaderError as exc:
                                raise salt.exceptions.SaltSystemExit(exc)
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
                                ret.update(full_ret)
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
                        sys.stderr.write('ERROR: Minions returned with non-zero exit code\n')
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
        not_response_minions = []
        not_connected_minions = []
        for each_minion in ret:
            minion_ret = ret[each_minion]
            if (
                    isinstance(minion_ret, string_types)
                    and minion_ret.startswith("Minion did not return")
                    ):
                if "Not connected" in minion_ret:
                    not_connected_minions.append(each_minion)
                elif "No response" in minion_ret:
                    not_response_minions.append(each_minion)
                not_return_counter += 1
                not_return_minions.append(each_minion)
            else:
                return_counter += 1
        print_cli('\n')
        print_cli('-------------------------------------------')
        print_cli('Summary')
        print_cli('-------------------------------------------')
        print_cli('# of minions targeted: {0}'.format(return_counter + not_return_counter))
        print_cli('# of minions returned: {0}'.format(return_counter))
        print_cli('# of minions that did not return: {0}'.format(not_return_counter))
        if self.options.verbose:
            if not_connected_minions:
                print_cli('Minions not connected: {0}'.format(" ".join(not_connected_minions)))
            if not_response_minions:
                print_cli('Minions not responding: {0}'.format(" ".join(not_response_minions)))
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
            try:
                self.progress_bar = salt.output.get_progress(self.config, out, progress)
            except Exception as exc:
                raise salt.exceptions.LoaderError('\nWARNING: Install the `progressbar` python package. '
                                                  'Requested job was still run but output cannot be displayed.\n')
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
            sys.stderr.write('ERROR: No return received\n')
            sys.exit(2)

    def _format_ret(self, full_ret):
        '''
        Take the full return data and format it to simple output
        '''
        ret = {}
        out = ''
        retcode = 0
        for key, data in six.iteritems(full_ret):
            ret[key] = data['ret']
            if 'out' in data:
                out = data['out']
            ret_retcode = salt.utils.job.get_retcode(data)
            if ret_retcode > retcode:
                retcode = ret_retcode
        return ret, out, retcode

    def _format_error(self, minion_error):
        for minion, error_doc in six.iteritems(minion_error):
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
            salt.output.display_output(fun + ':', 'nested', self.config)
            print_cli(docs[fun])
            print_cli('')
