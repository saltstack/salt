# -*- coding: utf-8 -*-
'''
Execute salt convenience routines
'''

# Import python libs
from __future__ import print_function
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
from salt.utils.event import tagify

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
        self.event = salt.utils.event.get_event('master', self.opts['sock_dir'], self.opts['transport'])

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
        if kwarg is None:
            kwarg = {}
        if not isinstance(kwarg, dict):
            raise salt.exceptions.SaltInvocationError(
                'kwarg must be formatted as a dictionary'
            )

        if pub_data is None:
            pub_data = {}
        if not isinstance(pub_data, dict):
            raise salt.exceptions.SaltInvocationError(
                'pub_data must be formatted as a dictionary'
            )

        arglist = salt.utils.args.parse_input(arg)

        def _append_kwarg(arglist, kwarg):
            '''
            Append the kwarg dict to the arglist
            '''
            kwarg['__kwarg__'] = True
            arglist.append(kwarg)

        if kwarg:
            try:
                if isinstance(arglist[-1], dict) \
                        and '__kwarg__' in arglist[-1]:
                    for key, val in kwarg.iteritems():
                        if key in arglist[-1]:
                            log.warning(
                                'Overriding keyword argument {0!r}'.format(key)
                            )
                        arglist[-1][key] = val
                else:
                    # No kwargs yet present in arglist
                    _append_kwarg(arglist, kwarg)
            except IndexError:
                # arglist is empty, just append
                _append_kwarg(arglist, kwarg)

        self._verify_fun(fun)
        args, kwargs = salt.minion.load_args_and_kwargs(
            self.functions[fun], arglist, pub_data
        )
        return self.functions[fun](*args, **kwargs)

    def master_call(self, **kwargs):
        '''
        Execute a runner function through the master network interface (eauth).
        '''
        load = kwargs
        load['cmd'] = 'runner'
        sreq = salt.transport.Channel.factory(self.opts,
                                              crypt='clear',
                                              usage='master_call')
        ret = sreq.send(load)
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
        ret_tag = tagify('ret', base=job['tag'])

        timelimit = time.time() + (timeout or 300)
        while True:
            ret = self.event.get_event(full=True)
            if ret is None:
                if time.time() > timelimit:
                    raise salt.exceptions.SaltClientTimeout(
                        "RunnerClient job '{0}' timed out".format(job['jid']),
                        jid=job['jid'])
                else:
                    continue

            if ret['tag'] == ret_tag:
                return ret['data']['return']


class Runner(RunnerClient):
    '''
    Execute the salt runner interface
    '''
    def _print_docs(self):
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
        if self.opts.get('doc', False):
            self._print_docs()
        else:
            try:
                return super(Runner, self).cmd(
                        self.opts['fun'], self.opts['arg'], self.opts)
            except salt.exceptions.SaltException as exc:
                ret = str(exc)
                print(ret)
                return ret
