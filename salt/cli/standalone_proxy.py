# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function
import sys
sys.modules['pkg_resources'] = None
import os
import time
import multiprocessing

# Import Salt libs
import salt.utils.job
import salt.utils.parsers
import salt.utils.stringutils
from salt.scripts import standalone_proxy_process
from salt.utils.args import yamlify_arg
from salt.utils.verify import verify_log
from salt.exceptions import (
    EauthAuthenticationError,
    LoaderError,
    SaltClientError,
    SaltInvocationError,
    SaltSystemExit
)

# Import 3rd-party libs
from salt.ext import six


class StandaloneProxyMinionCMD(salt.utils.parsers.SaltCMDOptionParser):
    '''
    The execution of a salt command happens here
    '''

    def run(self):
        '''
        Execute the salt command line
        '''
        import salt.client
        self.parse_args()

        # Setup file logging!
        self.setup_logfile_logger()
        verify_log(self.config)

        try:
            # We don't need to bail on config file permission errors
            # if the CLI process is run with the -a flag
            skip_perm_errors = self.options.eauth != ''

            self.local_client = salt.client.get_local_client(
                self.get_config_file_path(),
                skip_perm_errors=skip_perm_errors,
                auto_reconnect=True)
        except SaltClientError as exc:
            self.exit(2, '{0}\n'.format(exc))
            return

        minion_list = self._preview_target()
        if self.options.preview_target:
            self._output_ret(minion_list, self.config.get('output', 'nested'))
            return

        if self.options.batch or self.options.static:
            # _run_batch() will handle all output and
            # exit with the appropriate error condition
            # Execution will not continue past this point
            # in batch mode.
            self._run_batch()
            return

        # Determine what minions should execute against,
        # Eventually using cached data.
        self.processes = []
        for proxy_id in minion_list:
            process = multiprocessing.Process(target=standalone_proxy_process,
                                              args=(proxy_id,))
            process.start()
            self.processes.append(process)

        time.sleep(self.config.get('standalone_proxy_wait_time', 5))

        if self.options.timeout <= 0:
            self.options.timeout = self.local_client.opts['timeout']

        kwargs = {
            'tgt': self.config['tgt'],
            'fun': self.config['fun'],
            'arg': self.config['arg'],
            'timeout': self.options.timeout,
            'show_timeout': self.options.show_timeout,
            'show_jid': self.options.show_jid}

        if 'token' in self.config:
            import salt.utils.files
            try:
                with salt.utils.files.fopen(os.path.join(self.config['key_dir'], '.root_key'), 'r') as fp_:
                    kwargs['key'] = fp_.readline()
            except IOError:
                kwargs['token'] = self.config['token']

        kwargs['delimiter'] = self.options.delimiter

        if self.selected_target_option:
            kwargs['tgt_type'] = self.selected_target_option
        else:
            kwargs['tgt_type'] = 'glob'

        # If batch_safe_limit is set, check minions matching target and
        # potentially switch to batch execution
        if self.options.batch_safe_limit > 1:
            if len(self._preview_target()) >= self.options.batch_safe_limit:
                salt.utils.stringutils.print_cli('\nNOTICE: Too many minions targeted, switching to batch execution.')
                self.options.batch = self.options.batch_safe_size
                self._run_batch()
                return

        if getattr(self.options, 'return'):
            kwargs['ret'] = getattr(self.options, 'return')

        if getattr(self.options, 'return_config'):
            kwargs['ret_config'] = getattr(self.options, 'return_config')

        if getattr(self.options, 'return_kwargs'):
            kwargs['ret_kwargs'] = yamlify_arg(
                    getattr(self.options, 'return_kwargs'))

        if getattr(self.options, 'module_executors'):
            kwargs['module_executors'] = yamlify_arg(getattr(self.options, 'module_executors'))

        if getattr(self.options, 'executor_opts'):
            kwargs['executor_opts'] = yamlify_arg(getattr(self.options, 'executor_opts'))

        if getattr(self.options, 'metadata'):
            kwargs['metadata'] = yamlify_arg(
                    getattr(self.options, 'metadata'))

        # If using eauth and a token hasn't already been loaded into
        # kwargs, prompt the user to enter auth credentials
        if 'token' not in kwargs and 'key' not in kwargs and self.options.eauth:
            # This is expensive. Don't do it unless we need to.
            import salt.auth
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
            jid = self.local_client.cmd_async(**kwargs)
            salt.utils.stringutils.print_cli('Executed command with job ID: {0}'.format(jid))
            return

        # local will be None when there was an error
        if not self.local_client:
            return

        retcodes = []
        errors = []

        try:
            if self.options.subset:
                cmd_func = self.local_client.cmd_subset
                kwargs['sub'] = self.options.subset
                kwargs['cli'] = True
            else:
                cmd_func = self.local_client.cmd_cli

            if self.options.progress:
                kwargs['progress'] = True
                self.config['progress'] = True
                ret = {}
                for progress in cmd_func(**kwargs):
                    out = 'progress'
                    try:
                        self._progress_ret(progress, out)
                    except LoaderError as exc:
                        raise SaltSystemExit(exc)
                    if 'return_count' not in progress:
                        ret.update(progress)
                self._progress_end(out)
                self._print_returns_summary(ret)
            elif self.config['fun'] == 'sys.doc':
                ret = {}
                out = ''
                for full_ret in self.local_client.cmd_cli(**kwargs):
                    ret_, out, retcode = self._format_ret(full_ret)
                    ret.update(ret_)
                self._output_ret(ret, out)
            else:
                _ret = cmd_func(**kwargs)
                if self.options.verbose:
                    kwargs['verbose'] = True
                ret = {}
                for full_ret in _ret:
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
            self._output_ret(ret, '')
        finally:
            for process in self.processes:
                process.terminate()


    def _preview_target(self):
        '''
        Return a list of minions from a given target
        '''
        return self.local_client.gather_minions(self.config['tgt'], self.selected_target_option or 'glob')

    def _run_batch(self):
        import salt.cli.batch
        eauth = {}
        if 'token' in self.config:
            eauth['token'] = self.config['token']

        # If using eauth and a token hasn't already been loaded into
        # kwargs, prompt the user to enter auth credentials
        if 'token' not in eauth and self.options.eauth:
            # This is expensive. Don't do it unless we need to.
            import salt.auth
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

            try:
                batch = salt.cli.batch.Batch(self.config, eauth=eauth, quiet=True)
            except SaltClientError:
                sys.exit(2)

            ret = {}

            for res in batch.run():
                ret.update(res)

            self._output_ret(ret, '')

        else:
            try:
                self.config['batch'] = self.options.batch
                batch = salt.cli.batch.Batch(self.config, eauth=eauth, parser=self.options)
            except SaltClientError:
                # We will print errors to the console further down the stack
                sys.exit(1)
            # Printing the output is already taken care of in run() itself
            retcode = 0
            for res in batch.run():
                for ret in six.itervalues(res):
                    job_retcode = salt.utils.job.get_retcode(ret)
                    if job_retcode > retcode:
                        # Exit with the highest retcode we find
                        retcode = job_retcode
            sys.exit(retcode)

    def _print_errors_summary(self, errors):
        if errors:
            salt.utils.stringutils.print_cli('\n')
            salt.utils.stringutils.print_cli('---------------------------')
            salt.utils.stringutils.print_cli('Errors')
            salt.utils.stringutils.print_cli('---------------------------')
            for error in errors:
                salt.utils.stringutils.print_cli(self._format_error(error))

    def _print_returns_summary(self, ret):
        '''
        Display returns summary
        '''
        return_counter = 0
        not_return_counter = 0
        not_return_minions = []
        not_response_minions = []
        not_connected_minions = []
        failed_minions = []
        for each_minion in ret:
            minion_ret = ret[each_minion]
            if isinstance(minion_ret, dict) and 'ret' in minion_ret:
                minion_ret = ret[each_minion].get('ret')
            if (
                    isinstance(minion_ret, six.string_types)
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
                if self._get_retcode(ret[each_minion]):
                    failed_minions.append(each_minion)
        salt.utils.stringutils.print_cli('\n')
        salt.utils.stringutils.print_cli('-------------------------------------------')
        salt.utils.stringutils.print_cli('Summary')
        salt.utils.stringutils.print_cli('-------------------------------------------')
        salt.utils.stringutils.print_cli('# of minions targeted: {0}'.format(return_counter + not_return_counter))
        salt.utils.stringutils.print_cli('# of minions returned: {0}'.format(return_counter))
        salt.utils.stringutils.print_cli('# of minions that did not return: {0}'.format(not_return_counter))
        salt.utils.stringutils.print_cli('# of minions with errors: {0}'.format(len(failed_minions)))
        if self.options.verbose:
            if not_connected_minions:
                salt.utils.stringutils.print_cli('Minions not connected: {0}'.format(" ".join(not_connected_minions)))
            if not_response_minions:
                salt.utils.stringutils.print_cli('Minions not responding: {0}'.format(" ".join(not_response_minions)))
            if failed_minions:
                salt.utils.stringutils.print_cli('Minions with failures: {0}'.format(" ".join(failed_minions)))
        salt.utils.stringutils.print_cli('-------------------------------------------')

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
            except Exception:
                raise LoaderError('\nWARNING: Install the `progressbar` python package. '
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
            ret_retcode = self._get_retcode(data)
            if ret_retcode > retcode:
                retcode = ret_retcode
        return ret, out, retcode

    def _get_retcode(self, ret):
        '''
        Determine a retcode for a given return
        '''
        retcode = 0
        # if there is a dict with retcode, use that
        if isinstance(ret, dict) and ret.get('retcode', 0) != 0:
            return ret['retcode']
        # if its a boolean, False means 1
        elif isinstance(ret, bool) and not ret:
            return 1
        return retcode

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
        if isinstance(ret, six.string_types):
            self.exit(2, '{0}\n'.format(ret))
        for host in ret:
            if isinstance(ret[host], six.string_types) \
                    and (ret[host].startswith("Minion did not return")
                         or ret[host] == 'VALUE TRIMMED'):
                continue
            for fun in ret[host]:
                if fun not in docs and ret[host][fun]:
                    docs[fun] = ret[host][fun]
        if self.options.output:
            for fun in sorted(docs):
                salt.output.display_output({fun: docs[fun]}, 'nested', self.config)
        else:
            for fun in sorted(docs):
                salt.utils.stringutils.print_cli('{0}:'.format(fun))
                salt.utils.stringutils.print_cli(docs[fun])
                salt.utils.stringutils.print_cli('')
