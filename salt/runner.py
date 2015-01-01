# -*- coding: utf-8 -*-
'''
Execute salt convenience routines
'''

# Import python libs
from __future__ import print_function
from __future__ import absolute_import
import collections
import logging
import time

# Import salt libs
import salt.exceptions
import salt.loader
import salt.minion
import salt.utils
import salt.utils.args
import salt.utils.event
from salt.client import mixins
from salt.output import display_output
from salt.utils.error import raise_error

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
        self.functions = salt.loader.runner(opts)  # Must be self.functions for mixin to work correctly :-/
        self.returners = salt.loader.returners(opts, self.functions)
        self.outputters = salt.loader.outputters(opts)
        self.event = salt.utils.event.get_master_event(self.opts, self.opts['sock_dir'])

    def cmd(self, fun, arg, pub_data=None, kwarg=None):
        '''
        Execute a runner function

        .. code-block:: python

            >>> opts = salt.config.master_config('/etc/salt/master')
            >>> runner = salt.runner.RunnerClient(opts)
            >>> runner.cmd('jobs.list_jobs', [])
            {
                '20131219215650131543': {
                    'Arguments': [300],
                    'Function': 'test.sleep',
                    'StartTime': '2013, Dec 19 21:56:50.131543',
                    'Target': '*',
                    'Target-type': 'glob',
                    'User': 'saltdev'
                },
                '20131219215921857715': {
                    'Arguments': [300],
                    'Function': 'test.sleep',
                    'StartTime': '2013, Dec 19 21:59:21.857715',
                    'Target': '*',
                    'Target-type': 'glob',
                    'User': 'saltdev'
                },
            }

        '''
        if pub_data is None:
            pub_data = {}
        if not isinstance(pub_data, dict):
            raise salt.exceptions.SaltInvocationError(
                'pub_data must be formatted as a dictionary'
            )
        if kwarg is None:
            kwarg = {}
        if not isinstance(kwarg, dict):
            raise salt.exceptions.SaltInvocationError(
                'kwarg must be formatted as a dictionary'
            )
        arglist = salt.utils.args.parse_input(arg)

        # if you were passed kwarg, add it to arglist
        if kwarg:
            kwarg['__kwarg__'] = True
            arglist.append(kwarg)

        args, kwargs = salt.minion.load_args_and_kwargs(
            self.functions[fun], arglist, pub_data
        )
        low = {'fun': fun,
               'args': args,
               'kwargs': kwargs}
        return self.low(fun, low)

    def master_call(self, **kwargs):
        '''
        Execute a runner function through the master network interface (eauth).
        '''
        load = kwargs
        load['cmd'] = 'runner'
        channel = salt.transport.Channel.factory(self.opts,
                                                 crypt='clear',
                                                 usage='master_call')
        ret = channel.send(load)
        if isinstance(ret, collections.Mapping):
            if 'error' in ret:
                raise_error(**ret['error'])
        return ret

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
        reformatted_low = {'fun': low.pop('fun')}
        reformatted_low.update(auth_creds)
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
        return self.master_call(**reformatted_low)

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
        job = self.master_call(**reformatted_low)
        ret_tag = salt.utils.event.tagify('ret', base=job['tag'])

        if timeout is None:
            timeout = 300
        ret = self.event.get_event(tag=ret_tag, full=True, wait=timeout)
        if ret is None:
            raise salt.exceptions.SaltClientTimeout(
                "RunnerClient job '{0}' timed out".format(job['jid']),
                jid=job['jid'])

        return ret['data']['return']


class Runner(RunnerClient):
    '''
    Execute the salt runner interface
    '''
    def print_docs(self):
        '''
        Print out the documentation!
        '''
        arg = self.opts.get('fun', None)
        docs = super(Runner, self).get_docs(arg)
        for fun in sorted(docs):
            display_output('{0}:'.format(fun), 'text', self.opts)
            print(docs[fun])

    def run(self):
        '''
        Execute the runner sequence
        '''
        ret = {}
        if self.opts.get('doc', False):
            self.print_docs()
        else:
            try:
                low = {'fun': self.opts['fun']}
                args, kwargs = salt.minion.load_args_and_kwargs(
                    self.functions[low['fun']],
                    salt.utils.args.parse_input(self.opts['arg']),
                )
                low['args'] = args
                low['kwargs'] = kwargs

                async_pub = super(Runner, self).async(self.opts['fun'], low)
                # Run the runner!
                if self.opts.get('async', False):
                    log.info('Running in async mode. Results of this execution may '
                             'be collected by attaching to the master event bus or '
                             'by examing the master job cache, if configured. '
                             'This execution is running in pid {pid} under tag {tag}'.format(**async_pub))
                    exit(0)  # TODO: return or something? Don't like exiting...

                # output rets if you have some

                if not self.opts.get('quiet', False):
                    for suffix, ret in self.get_async_returns(async_pub['tag']):
                        # skip "new" events
                        if suffix == 'new':
                            continue
                        if isinstance(ret, dict) and 'outputter' in ret and ret['outputter'] is not None:
                            print(self.outputters[ret['outputter']](ret['data']))
                        else:
                            salt.output.display_output(ret, '', self.opts)


            except salt.exceptions.SaltException as exc:
                ret = str(exc)
                if not self.opts.get('quiet', False):
                    print(ret)
                return ret
            log.debug('Runner return: {0}'.format(ret))
            return ret
