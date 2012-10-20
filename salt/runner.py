'''
Execute salt convenience routines
'''

import sys

# Import salt modules
import salt.loader
import salt.exceptions
import salt.utils


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
                for fun in sorted(self.functions)
                if fun.startswith(self.opts['fun'])]

        return dict(ret)

    def cmd(self, fun, arg):
        '''
        Execute a runner with the given arguments
        '''
        self._verify_fun(fun)
        # pylint: disable-msg=W0142
        return self.functions[fun](*arg)

    def low(self, fun, low):
        '''
        Pass in the runner function name and the low data structure
        '''
        l_fun = self.functions[fun]
        fcall = salt.utils.format_call(l_fun, low)
        if 'kwargs' in fcall:
            ret = l_fun(*fcall['args'], **fcall['kwargs'])
        else:
            ret = l_fun(*f_call['args'])
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

        for fun, doc in ret.items():
            print("{0}:\n{1}\n".format(fun, doc))

    def run(self):
        '''
        Execute the runner sequence
        '''
        if self.opts.get('doc', False):
            self._print_docs()
        else:
            try:
                return super(Runner, self).cmd(
                        self.opts['fun'], self.opts['arg'])
            except salt.exceptions.SaltException as exc:
                sys.stderr.write('{0}\n'.format(exc))
                sys.exit(1)
