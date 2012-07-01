'''
The caller module is used as a front-end to manage direct calls to the salt
minion modules.
'''

# Import python modules
import sys
import logging
import traceback

# Import salt libs
import salt
import salt.utils
import salt.loader
import salt.minion
from salt._compat import string_types

# Custom exceptions
from salt.exceptions import (
    SaltClientError,
    CommandNotFoundError,
    CommandExecutionError,
)


class Caller(object):
    '''
    Object to wrap the calling of local salt modules for the salt-call command
    '''
    def __init__(self, opts):
        '''
        Pass in the command line options
        '''
        self.opts = opts
        # Handle this here so other deeper code which might
        # be imported as part of the salt api doesn't do  a
        # nasty sys.exit() and tick off our developer users
        try:
            self.minion = salt.minion.SMinion(opts)
        except SaltClientError as exc:
            raise SystemExit(str(exc))

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
            args, kw = salt.minion.detect_kwargs(
                self.minion.functions[fun], self.opts['arg'])
            ret['return'] = self.minion.functions[fun](*args, **kw)
        except (TypeError, CommandExecutionError) as exc:
            msg = 'Error running \'{0}\': {1}\n'
            if self.opts['log_level'] <= logging.DEBUG:
                sys.stderr.write(traceback.format_exc())
            sys.stderr.write(msg.format(fun, str(exc)))
            sys.exit(1)
        except CommandNotFoundError as exc:
            msg = 'Command required for \'{0}\' not found: {1}\n'
            sys.stderr.write(msg.format(fun, str(exc)))
            sys.exit(1)
        if hasattr(self.minion.functions[fun], '__outputter__'):
            oput = self.minion.functions[fun].__outputter__
            if isinstance(oput, string_types):
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
                print('{0}:\n{1}\n'.format(name, docs[name]))

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
            color = not bool(self.opts['no_color'])
            printout({'local': ret['return']}, color=color)
