# -*- coding: utf-8 -*-
'''
Execute salt convenience routines
'''

# Import python libs
from __future__ import absolute_import, print_function
import os
import logging

# Import salt libs
import salt.exceptions
import salt.loader
import salt.minion
import salt.utils  # Can be removed when get_specific_user is moved
import salt.utils.args
import salt.utils.event
import salt.utils.files
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
    client = u'runner'
    tag_prefix = u'run'

    def __init__(self, opts):
        self.opts = opts

    @property
    def functions(self):
        if not hasattr(self, u'_functions'):
            if not hasattr(self, u'utils'):
                self.utils = salt.loader.utils(self.opts)
            # Must be self.functions for mixin to work correctly :-/
            try:
                self._functions = salt.loader.runner(self.opts, utils=self.utils)
            except AttributeError:
                # Just in case self.utils is still not present (perhaps due to
                # problems with the loader), load the runner funcs without them
                self._functions = salt.loader.runner(self.opts)

        return self._functions

    def _reformat_low(self, low):
        '''
        Format the low data for RunnerClient()'s master_call() function

        This also normalizes the following low data formats to a single, common
        low data structure.

        Old-style low: ``{'fun': 'jobs.lookup_jid', 'jid': '1234'}``
        New-style: ``{'fun': 'jobs.lookup_jid', 'kwarg': {'jid': '1234'}}``
        CLI-style: ``{'fun': 'jobs.lookup_jid', 'arg': ['jid="1234"']}``
        '''
        fun = low.pop(u'fun')
        verify_fun(self.functions, fun)

        eauth_creds = dict([(i, low.pop(i)) for i in [
            u'username', u'password', u'eauth', u'token', u'client', u'user', u'key',
        ] if i in low])

        # Run name=value args through parse_input. We don't need to run kwargs
        # through because there is no way to send name=value strings in the low
        # dict other than by including an `arg` array.
        _arg, _kwarg = salt.utils.args.parse_input(
                low.pop(u'arg', []), condition=False)
        _kwarg.update(low.pop(u'kwarg', {}))

        # If anything hasn't been pop()'ed out of low by this point it must be
        # an old-style kwarg.
        _kwarg.update(low)

        # Finally, mung our kwargs to a format suitable for the byzantine
        # load_args_and_kwargs so that we can introspect the function being
        # called and fish for invalid kwargs.
        munged = []
        munged.extend(_arg)
        munged.append(dict(__kwarg__=True, **_kwarg))
        arg, kwarg = salt.minion.load_args_and_kwargs(
            self.functions[fun],
            munged,
            self.opts,
            ignore_invalid=True)

        return dict(fun=fun, kwarg={u'kwarg': kwarg, u'arg': arg},
                **eauth_creds)

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

    def cmd_sync(self, low, timeout=None, full_return=False):
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
        return mixins.SyncClientMixin.cmd_sync(self, reformatted_low, timeout, full_return)

    def cmd(self, fun, arg=None, pub_data=None, kwarg=None, print_event=True, full_return=False):
        '''
        Execute a function
        '''
        return super(RunnerClient, self).cmd(fun,
                                             arg,
                                             pub_data,
                                             kwarg,
                                             print_event,
                                             full_return)


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
        arg = self.opts.get(u'fun', None)
        docs = super(Runner, self).get_docs(arg)
        for fun in sorted(docs):
            display_output(u'{0}:'.format(fun), u'text', self.opts)
            print(docs[fun])

    # TODO: move to mixin whenever we want a salt-wheel cli
    def run(self):
        '''
        Execute the runner sequence
        '''
        import salt.minion
        ret = {}
        if self.opts.get(u'doc', False):
            self.print_docs()
        else:
            low = {u'fun': self.opts[u'fun']}
            try:
                # Allocate a jid
                async_pub = self._gen_async_pub()
                self.jid = async_pub[u'jid']

                fun_args = salt.utils.args.parse_input(
                        self.opts[u'arg'],
                        no_parse=self.opts.get(u'no_parse', []))

                verify_fun(self.functions, low[u'fun'])
                args, kwargs = salt.minion.load_args_and_kwargs(
                    self.functions[low[u'fun']],
                    fun_args,
                    self.opts,
                )
                low[u'arg'] = args
                low[u'kwarg'] = kwargs

                if self.opts.get(u'eauth'):
                    if u'token' in self.opts:
                        try:
                            with salt.utils.files.fopen(os.path.join(self.opts[u'cachedir'], u'.root_key'), u'r') as fp_:
                                low[u'key'] = fp_.readline()
                        except IOError:
                            low[u'token'] = self.opts[u'token']

                    # If using eauth and a token hasn't already been loaded into
                    # low, prompt the user to enter auth credentials
                    if u'token' not in low and u'key' not in low and self.opts[u'eauth']:
                        # This is expensive. Don't do it unless we need to.
                        import salt.auth
                        resolver = salt.auth.Resolver(self.opts)
                        res = resolver.cli(self.opts[u'eauth'])
                        if self.opts[u'mktoken'] and res:
                            tok = resolver.token_cli(
                                    self.opts[u'eauth'],
                                    res
                                    )
                            if tok:
                                low[u'token'] = tok.get(u'token', u'')
                        if not res:
                            log.error(u'Authentication failed')
                            return ret
                        low.update(res)
                        low[u'eauth'] = self.opts[u'eauth']
                else:
                    user = salt.utils.get_specific_user()

                if low[u'fun'] == u'state.orchestrate':
                    low[u'kwarg'][u'orchestration_jid'] = async_pub[u'jid']

                # Run the runner!
                if self.opts.get(u'async', False):
                    if self.opts.get(u'eauth'):
                        async_pub = self.cmd_async(low)
                    else:
                        async_pub = self.async(self.opts[u'fun'],
                                               low,
                                               user=user,
                                               pub=async_pub)
                    # by default: info will be not enougth to be printed out !
                    log.warning(
                        u'Running in async mode. Results of this execution may '
                        u'be collected by attaching to the master event bus or '
                        u'by examing the master job cache, if configured. '
                        u'This execution is running under tag %s', async_pub[u'tag']
                    )
                    return async_pub[u'jid']  # return the jid

                # otherwise run it in the main process
                if self.opts.get(u'eauth'):
                    ret = self.cmd_sync(low)
                    if isinstance(ret, dict) and set(ret) == set((u'data', u'outputter')):
                        outputter = ret[u'outputter']
                        ret = ret[u'data']
                    else:
                        outputter = None
                    display_output(ret, outputter, self.opts)
                else:
                    ret = self._proc_function(self.opts[u'fun'],
                                              low,
                                              user,
                                              async_pub[u'tag'],
                                              async_pub[u'jid'],
                                              daemonize=False)
            except salt.exceptions.SaltException as exc:
                evt = salt.utils.event.get_event(u'master', opts=self.opts)
                evt.fire_event({u'success': False,
                                u'return': u'{0}'.format(exc),
                                u'retcode': 254,
                                u'fun': self.opts[u'fun'],
                                u'fun_args': fun_args,
                                u'jid': self.jid},
                               tag=u'salt/run/{0}/ret'.format(self.jid))
                # Attempt to grab documentation
                if u'fun' in low:
                    ret = self.get_docs(u'{0}*'.format(low[u'fun']))
                else:
                    ret = None

                # If we didn't get docs returned then
                # return the `not availble` message.
                if not ret:
                    ret = u'{0}'.format(exc)
                if not self.opts.get(u'quiet', False):
                    display_output(ret, u'nested', self.opts)
            else:
                log.debug(u'Runner return: %s', ret)

            return ret
