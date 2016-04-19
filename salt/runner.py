# -*- coding: utf-8 -*-
'''
Execute salt convenience routines
'''

# Import python libs
from __future__ import absolute_import, print_function
import logging

# Import salt libs
import salt.exceptions
import salt.loader
import salt.minion
import salt.utils.args
import salt.utils.event
from salt.client import mixins
from salt.output import display_output
from salt.utils.lazy import verify_fun

log = logging.getLogger(__name__)


class RunnerClient(mixins.SyncClientMixin, mixins.AsyncClientMixin, object):
    '''
    The interface used by the :command:`salt-run` CLI tool on the Salt Master

    It executes :ref:`runner modules <all-salt.runners>` which run on the Salt
    Master.

    Importing and using ``RunnerClient`` must be done on the same machine as
    the Salt Master and it must be done using the same user that the Salt
    Master is running as.

    Salt's :conf_master:`external_auth` can be used to authenticate calls. The
    eauth user must be authorized to execute runner modules: (``@runner``).
    Only the :py:meth:`master_call` below supports eauth.
    '''
    client = 'runner'
    tag_prefix = 'run'

    def __init__(self, opts):
        self.opts = opts

    @property
    def functions(self):
        if not hasattr(self, '_functions'):
            self._functions = salt.loader.runner(self.opts)  # Must be self.functions for mixin to work correctly :-/
        return self._functions

    def _reformat_low(self, low):
        '''
        Format the low data for RunnerClient()'s master_call() function

        The master_call function here has a different function signature than
        on WheelClient. So extract all the eauth keys and the fun key and
        assume everything else is a kwarg to pass along to the runner function
        to be called.
        '''
        auth_creds = dict([(i, low.pop(i)) for i in [
                'username', 'password', 'eauth', 'token', 'client',
            ] if i in low])
        fun = low.pop('fun')
        reformatted_low = {'fun': fun}
        reformatted_low.update(auth_creds)
        # Support old style calls where arguments could be specified in 'low' top level
        if not low.get('args') and not low.get('kwargs'):  # not specified or empty
            verify_fun(self.functions, fun)
            merged_args_kwargs = salt.utils.args.condition_input([], low)
            parsed_input = salt.utils.args.parse_input(merged_args_kwargs)
            args, kwargs = salt.minion.load_args_and_kwargs(
                self.functions[fun],
                parsed_input,
                self.opts,
                ignore_invalid=True
            )
            low['args'] = args
            low['kwargs'] = kwargs
        if 'kwargs' not in low:
            low['kwargs'] = {}
        if 'args' not in low:
            low['args'] = []
        reformatted_low['kwarg'] = low
        return reformatted_low

    def cmd_async(self, low):
        '''
        Execute a runner function asynchronously; eauth is respected

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized to execute runner functions: (``@runner``).

        .. code-block:: python

            runner.eauth_async({
                'fun': 'jobs.list_jobs',
                'username': 'saltdev',
                'password': 'saltdev',
                'eauth': 'pam',
            })
        '''
        reformatted_low = self._reformat_low(low)

        return mixins.AsyncClientMixin.cmd_async(self, reformatted_low)

    def cmd_sync(self, low, timeout=None):
        '''
        Execute a runner function synchronously; eauth is respected

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized to execute runner functions: (``@runner``).

        .. code-block:: python

            runner.eauth_sync({
                'fun': 'jobs.list_jobs',
                'username': 'saltdev',
                'password': 'saltdev',
                'eauth': 'pam',
            })
        '''
        reformatted_low = self._reformat_low(low)
        return mixins.SyncClientMixin.cmd_sync(self, reformatted_low, timeout)


class Runner(RunnerClient):
    '''
    Execute the salt runner interface
    '''
    def __init__(self, opts):
        super(Runner, self).__init__(opts)
        self.returners = salt.loader.returners(opts, self.functions)
        self.outputters = salt.loader.outputters(opts)

    def print_docs(self):
        '''
        Print out the documentation!
        '''
        arg = self.opts.get('fun', None)
        docs = super(Runner, self).get_docs(arg)
        for fun in sorted(docs):
            display_output('{0}:'.format(fun), 'text', self.opts)
            print(docs[fun])

    # TODO: move to mixin whenever we want a salt-wheel cli
    def run(self):
        '''
        Execute the runner sequence
        '''
        ret, async_pub = {}, {}
        if self.opts.get('doc', False):
            self.print_docs()
        else:
            low = {'fun': self.opts['fun']}
            try:
                verify_fun(self.functions, low['fun'])
                args, kwargs = salt.minion.load_args_and_kwargs(
                    self.functions[low['fun']],
                    salt.utils.args.parse_input(self.opts['arg']),
                    self.opts,
                )
                low['args'] = args
                low['kwargs'] = kwargs

                user = salt.utils.get_specific_user()

                # Run the runner!
                if self.opts.get('async', False):
                    async_pub = self.async(self.opts['fun'], low, user=user)
                    # by default: info will be not enougth to be printed out !
                    log.warning('Running in async mode. Results of this execution may '
                             'be collected by attaching to the master event bus or '
                             'by examing the master job cache, if configured. '
                             'This execution is running under tag {tag}'.format(**async_pub))
                    return async_pub['jid']  # return the jid

                # otherwise run it in the main process
                async_pub = self._gen_async_pub()
                ret = self._proc_function(self.opts['fun'],
                                          low,
                                          user,
                                          async_pub['tag'],
                                          async_pub['jid'],
                                          False)  # Don't daemonize
            except salt.exceptions.SaltException as exc:
                ret = '{0}'.format(exc)
                if not self.opts.get('quiet', False):
                    display_output(ret, 'nested', self.opts)
                return ret
            log.debug('Runner return: {0}'.format(ret))
            return ret
