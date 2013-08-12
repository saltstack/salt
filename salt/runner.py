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


class RunnerClient(object):
    '''
    A client for accessing runners
    '''
    def __init__(self, opts):
        self.opts = opts
        self.functions = salt.loader.runner(opts)

    def _proc_runner(self, tag, fun, low):
        '''
        Run this method in a multiprocess target to execute the runner in a
        multiprocess and fire the return data on the event bus
        '''
        salt.utils.daemonize()
        data = {}
        try:
            data['ret'] = self.low(fun, low)
        except Exception as exc:
            data['ret'] = 'Exception occured in runner {0}: {1}'.format(
                    fun,
                    exc,
                    )
        event = salt.utils.event.MasterEvent(self.opts['sock_dir'])
        event.fire_event(data, tag)

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

    def async(self, fun, low):
        '''
        Execute the runner in a multiprocess and return the event tag to use
        to watch for the return
        '''
        tag = '{0:%Y%m%d%H%M%S%f}'.format(datetime.datetime.now())
        tag = tag = '{0}r'.format(tag[:-1])
        proc = multiprocessing.Process(
                target=self._proc_runner,
                args=(tag, fun, low))
        proc.start()
        return tag

    def master_call(self, fun, **kwargs):
        '''
        Send a function call to a wheel module through the master network interface
        '''
        load = kwargs
        load['cmd'] = 'runner'
        load['fun'] = fun
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
