'''
Execute salt convenience routines
'''

# Import salt libs
import salt.loader
import salt.exceptions
import salt.utils
import salt.minion


class RunnerClient(object):
    '''
    A client for accessing runners
    '''
    def __init__(self, opts):
        self.opts = opts
        self.functions = salt.loader.runner(opts)

    def _verify_fun(self, fun):
        '''
        Check that the function passed really exists
        '''
        if fun not in self.functions:
            err = "Function '{0}' is unavailable".format(fun)
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
        l_fun = self.functions[fun]
        f_call = salt.utils.format_call(l_fun, low)
        ret = l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))
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
            print("{0}:\n{1}\n".format(fun, ret[fun]))

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
