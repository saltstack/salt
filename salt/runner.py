# -*- coding: utf-8 -*-
'''
Execute salt convenience routines
'''

# Import python libs
from __future__ import print_function
import collections
import datetime
import logging
import multiprocessing
import time

# Import salt libs
import salt.exceptions
import salt.loader
import salt.minion
import salt.utils
import salt.utils.args
import salt.utils.event
from salt.output import display_output
from salt.utils.doc import strip_rst as _strip_rst
from salt.utils.error import raise_error
from salt.utils.event import tagify

log = logging.getLogger(__name__)


class RunnerClient(object):
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
    def __init__(self, opts):
        self.opts = opts
        self.functions = salt.loader.runner(opts)

    def _proc_runner(self, fun, low, user, tag, jid):
        '''
        Run this method in a multiprocess target to execute the runner in a
        multiprocess and fire the return data on the event bus
        '''
        salt.utils.daemonize()
        event = salt.utils.event.get_event(
                'master',
                self.opts['sock_dir'],
                self.opts['transport'],
                listen=False)
        data = {'fun': 'runner.{0}'.format(fun),
                'jid': jid,
                'user': user,
                }
        event.fire_event(data, tagify('new', base=tag))

        try:
            data['return'] = self.low(fun, low)
            data['success'] = True
        except Exception as exc:
            data['return'] = 'Exception occurred in runner {0}: {1}: {2}'.format(
                            fun,
                            exc.__class__.__name__,
                            exc,
                            )
            data['success'] = False
        data['user'] = user
        event.fire_event(data, tagify('ret', base=tag))
        # this is a workaround because process reaping is defeating 0MQ linger
        time.sleep(2.0)  # delay so 0MQ event gets out before runner process reaped

    def _verify_fun(self, fun):
        '''
        Check that the function passed really exists
        '''
        if fun not in self.functions:
            err = 'Function {0!r} is unavailable'.format(fun)
            raise salt.exceptions.CommandExecutionError(err)

    def get_docs(self, arg=None):
        '''
        Return a dictionary of functions and the inline documentation for each
        '''
        if arg:
            target_mod = arg + '.' if not arg.endswith('.') else arg
            docs = [(fun, self.functions[fun].__doc__)
                    for fun in sorted(self.functions)
                    if fun == arg or fun.startswith(target_mod)]
        else:
            docs = [(fun, self.functions[fun].__doc__)
                    for fun in sorted(self.functions)]
        docs = dict(docs)
        return _strip_rst(docs)

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

    def low(self, fun, low):
        '''
        Pass in the runner function name and the low data structure

        .. code-block:: python

            runner.low({'fun': 'jobs.lookup_jid', 'jid': '20131219215921857715'})
        '''
        self._verify_fun(fun)
        l_fun = self.functions[fun]
        f_call = salt.utils.format_call(l_fun, low)
        ret = l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))
        return ret

    def async(self, fun, low, user='UNKNOWN'):
        '''
        Execute the runner in a multiprocess and return the event tag to use
        to watch for the return
        '''
        jid = '{0:%Y%m%d%H%M%S%f}'.format(datetime.datetime.now())
        tag = tagify(jid, prefix='run')
        #low['tag'] = tag
        #low['jid'] = jid

        proc = multiprocessing.Process(
                target=self._proc_runner,
                args=(fun, low, user, tag, jid))
        proc.start()
        return {'tag': tag}

    def master_call(self, **kwargs):
        '''
        Execute a runner function through the master network interface (eauth).

        This function requires that :conf_master:`external_auth` is configured
        and the user is authorized to execute runner functions: (``@runner``).

        .. code-block:: python

            runner.master_call(
                fun='jobs.list_jobs',
                username='saltdev',
                password='saltdev',
                eauth='pam'
            )
        '''
        load = kwargs
        load['cmd'] = 'runner'
        # sreq = salt.payload.SREQ(
        #         'tcp://{0[interface]}:{0[ret_port]}'.format(self.opts),
        #        )
        sreq = salt.transport.Channel.factory(self.opts, crypt='clear')
        ret = sreq.send(load)
        if isinstance(ret, collections.Mapping):
            if 'error' in ret:
                raise_error(**ret['error'])
        return ret


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
