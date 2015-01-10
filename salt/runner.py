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
import sys
import multiprocessing

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
import salt.ext.six as six

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
                    for key, val in six.iteritems(kwarg):
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
        fstr = '{0}.prep_jid'.format(self.opts['master_job_cache'])
        jid = self.returners[fstr]()
        log.debug('Runner starting with jid {0}'.format(jid))
        self.event.fire_event({'runner_job': fun}, tagify([jid, 'new'], 'job'))
        target = RunnerClient._thread_return
        data = {'fun': fun, 'jid': jid, 'args': args, 'kwargs': kwargs}
        args = (self, self.opts, data)
        ret = jid
        if self.opts.get('async', False):
            process = multiprocessing.Process(
                target=target, args=args
            )
            process.start()
        else:
            ret = target(*args)
        return ret

    @classmethod
    def _thread_return(cls, instance, opts, data):
        '''
        The multiprocessing process calls back here
        to stream returns
        '''
        # Runners modules runtime injection:
        # - the progress event system with the correct jid
        # - Provide JID if the runner wants to access it directly
        done = {}
        if opts.get('async', False):
            progress = salt.utils.event.get_runner_event(opts, data['jid'], listen=False).fire_progress
        else:
            progress = _progress_print
        for func_name, func in instance.functions.items():
            if func.__module__ in done:
                continue
            mod = sys.modules[func.__module__]
            mod.__jid__ = data['jid']
            mod.__progress__ = progress
            done[func.__module__] = mod
        ret = instance.functions[data['fun']](*data['args'], **data['kwargs'])
        # Sleep for just a moment to let any progress events return
        time.sleep(0.1)
        ret_load = {'return': ret, 'fun': data['fun'], 'fun_args': data['args']}
        # Don't use the invoking processes' event socket because it could be closed down by the time we arrive here.
        # Create another, for safety's sake.
        master_event = salt.utils.event.get_master_event(opts, opts['sock_dir'], listen=False)
        master_event.fire_event(ret_load, tagify([data['jid'], 'return'], 'runner'))
        master_event.destroy()
        try:
            fstr = '{0}.save_runner_load'.format(opts['master_job_cache'])
            instance.returners[fstr](data['jid'], ret_load)
        except KeyError:
            log.debug(
                'The specified returner used for the master job cache '
                '"{0}" does not have a save_runner_load function! The results '
                'of this runner execution will not be stored.'.format(
                    opts['master_job_cache']
                )
            )
        except Exception:
            log.critical(
                'The specified returner threw a stack trace:\n',
                exc_info=True
            )
        if opts.get('async', False):
            return data['jid']
        else:
            return ret

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
        ret_tag = tagify('ret', base=job['tag'])

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
                # Run the runner!
                jid = super(Runner, self).cmd(
                    self.opts['fun'], self.opts['arg'], self.opts)
                if self.opts.get('async', False):
                    log.info('Running in async mode. Results of this execution may '
                             'be collected by attaching to the master event bus or '
                             'by examing the master job cache, if configured.')
                    rets = self.get_runner_returns(jid)
                else:
                    rets = [jid]
                # Gather the returns
                for ret in rets:
                    if not self.opts.get('quiet', False):
                        if isinstance(ret, dict) and 'outputter' in ret and ret['outputter'] is not None:
                            print(self.outputters[ret['outputter']](ret['data']))
                        else:
                            salt.output.display_output(ret, '', self.opts)

            except salt.exceptions.SaltException as exc:
                ret = str(exc)
                print(ret)
                return ret
            log.debug('Runner return: {0}'.format(ret))
            return ret

    def get_runner_returns(self, jid, timeout=None):
        '''
        Gather the return data from the event system, break hard when timeout
        is reached.
        '''
        if timeout is None:
            timeout = self.opts['timeout'] * 2

        timeout_at = time.time() + timeout
        last_progress_timestamp = time.time()

        while True:
            raw = self.event.get_event(timeout, full=True)
            time.sleep(0.1)
            # If we saw no events in the event bus timeout
            # OR
            # we have reached the total timeout
            # AND
            # have not seen any progress events for the length of the timeout.
            if raw is None and (time.time() > timeout_at and
                                time.time() - last_progress_timestamp > timeout):
                # Timeout reached
                break
            try:
                if not raw['tag'].split('/')[1] == 'runner' and raw['tag'].split('/')[2] == jid:
                    continue
                elif raw['tag'].split('/')[3] == 'progress' and raw['tag'].split('/')[2] == jid:
                    last_progress_timestamp = time.time()
                    yield {'data': raw['data']['data'], 'outputter': raw['data']['outputter']}
                elif raw['tag'].split('/')[3] == 'return' and raw['tag'].split('/')[2] == jid:
                    yield raw['data']['return']
                    break
                # Handle a findjob that might have been kicked off under the covers
                elif raw['data']['fun'] == 'saltutil.findjob':
                    timeout_at = timeout_at + 10
                    continue
            except (IndexError, KeyError):
                continue


def _progress_print(text, *args, **kwargs):
    print(text)
