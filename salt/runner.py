# -*- coding: utf-8 -*-
'''
Execute salt convenience routines
'''

# Import python libs
import multiprocessing
import datetime

# Import salt libs
import salt.loader
import salt.exceptions
import salt.utils
import salt.minion
import salt.utils.event
from salt.utils.event import tagify


class RunnerClient(object):
    '''
    ``RunnerClient`` is the same interface used by the :command:`salt-run`
    command-line tool on the Salt Master. It executes :ref:`runner modules
    <all-salt.runners>` which run on the Salt Master.

    Importing and using ``RunnerClient`` must be done on the same machine as
    the Salt Master and it must be done using the same user that the Salt
    Master is running as.
    '''
    def __init__(self, opts):
        self.opts = opts
        self.functions = salt.loader.runner(opts)

    def _proc_runner(self, tag, fun, low, user):
        '''
        Run this method in a multiprocess target to execute the runner in a
        multiprocess and fire the return data on the event bus
        '''
        salt.utils.daemonize()
        event = salt.utils.event.MasterEvent(self.opts['sock_dir'])
        data = {'fun': "runner.{0}".format(fun),
                'jid': low['jid'],
                'user': user,
                }
        event.fire_event(data, tagify('new', base=tag))

        try:
            data['ret'] = self.low(fun, low)
            data['success'] = True
        except Exception as exc:
            data['ret'] = 'Exception occured in runner {0}: {1}'.format(
                            fun,
                            exc,
                            )
        data['user'] = user
        event.fire_event(data, tagify('ret', base=tag))

    def _verify_fun(self, fun):
        '''
        Check that the function passed really exists
        '''
        if fun not in self.functions:
            err = 'Function {0!r} is unavailable'.format(fun)
            raise salt.exceptions.CommandExecutionError(err)

    def get_docs(self):
        '''
        Return a dictionary of functions and the inline documentation for each
        '''
        ret = [(fun, self.functions[fun].__doc__)
                for fun in sorted(self.functions)]

        return dict(ret)

    def cmd(self, fun, arg, kwarg=None):
        '''
        Execute a runner with the given arguments
        '''
        if not isinstance(kwarg, dict):
            kwarg = {}
        self._verify_fun(fun)
        args, kwargs = salt.minion.parse_args_and_kwargs(
                self.functions[fun],
                arg,
                kwarg)
        return self.functions[fun](*args, **kwargs)

    def low(self, fun, low):
        '''
        Pass in the runner function name and the low data structure
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
        low['tag'] = tag
        low['jid'] = jid

        proc = multiprocessing.Process(
                target=self._proc_runner,
                args=(tag, fun, low, user))
        proc.start()
        return tag

    def master_call(self, **kwargs):
        '''
        Send a function call to a runner module through the master network
        interface.
        Expects that one of the kwargs is key 'fun' whose value is the
        namestring of the function to call.
        '''
        load = kwargs
        load['cmd'] = 'runner'
        sreq = salt.payload.SREQ(
                'tcp://{0[interface]}:{0[ret_port]}'.format(self.opts),
                )
        ret = sreq.send('clear', load)
        if ret == '':
            raise salt.exceptions.EauthAuthenticationError
        return ret


class Runner(RunnerClient):
    '''
    Execute the salt runner interface
    '''
    def _print_docs(self):
        '''
        Print out the documentation!
        '''
        ret = super(Runner, self).get_docs()

        for fun in sorted(ret):
            print('{0}:\n{1}\n'.format(fun, ret[fun]))

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
                print ret
                return ret
