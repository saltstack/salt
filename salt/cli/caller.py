'''
The caller module is used as a front-end to manage direct calls to the salt
minion modules.
'''

# Import python modules
import sys

# Import salt libs
import salt
import salt.utils
import salt.loader
import salt.minion

# Custom exceptions
from salt.exceptions import CommandExecutionError, CommandNotFoundError

class Caller(object):
    '''
    Object to wrap the calling of local salt modules for the salt-call command
    '''
    def __init__(self, opts):
        '''
        Pass in the command line options
        '''
        self.opts = opts
        opts['grains'] = salt.loader.grains(opts)
        self.minion = salt.minion.SMinion(opts)

    def call(self):
        '''
        Call the module
        '''
        ret = {}
        fun = self.opts['fun']

        if fun not in self.minion.functions:
            sys.stderr.write('Function {0} is not available\n'.format(fun))
            sys.exit(1)
        try:
            ret['return'] = self.minion.functions[fun](
                    *self.opts['arg']
                    )
        except (TypeError, CommandExecutionError) as exc:
            msg = 'Error running \'{0}\': {1}\n'
            sys.stderr.write(msg.format(fun, str(exc)))
            sys.exit(1)
        except CommandNotFoundError as exc:
            msg = 'Command not found in \'{0}\': {1}\n'
            sys.stderr.write(msg.format(fun, str(exc)))
            sys.exit(1)
        if hasattr(self.minion.functions[fun], '__outputter__'):
            oput = self.minion.functions[fun].__outputter__
            if isinstance(oput, basestring):
                ret['out'] = oput
        return ret

    def print_docs(self):
        '''
        Pick up the documentation for all of the modules and print it out.
        '''
        docs = {}
        for name, func in self.minion.functions.items():
            if name not in docs:
                if func.__doc__:
                    docs[name] = func.__doc__
        for name in sorted(docs):
            if name.startswith(self.opts['fun']):
                print '{0}:\n{1}\n'.format(name, docs[name])

    def print_grains(self):
        '''
        Print out the grains
        '''
        grains = salt.loader.grains(self.opts)
        printout = self._get_outputter(out='yaml')
        # If --json-out is specified, pretty print it
        if 'json_out' in self.opts and self.opts['json_out']:
            printout.indent = 2
        printout(grains)

    def _get_outputter(self, out=None):
        get_outputter = salt.output.get_outputter
        if self.opts['raw_out']:
            printout = get_outputter('raw')
        elif self.opts['json_out']:
            printout = get_outputter('json')
        elif self.opts['txt_out']:
            printout = get_outputter('txt')
        elif self.opts['yaml_out']:
            printout = get_outputter('yaml')
        elif out:
            printout = get_outputter(out)
        else:
            printout = get_outputter(None)
        return printout

    def run(self):
        '''
        Execute the salt call logic
        '''
        if self.opts['doc']:
            self.print_docs()
        elif self.opts['grains_run']:
            self.print_grains()
        else:
            ret = self.call()
            # Determine the proper output method and run it
            if 'out' in ret:
                printout = self._get_outputter(ret['out'])
            else:
                printout = self._get_outputter()
            if 'json_out' in self.opts and self.opts['json_out']:
                printout.indent = 2

            printout({'local': ret['return']}, color=self.opts['color'])
