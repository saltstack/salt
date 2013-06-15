'''
The caller module is used as a front-end to manage direct calls to the salt
minion modules.
'''

# Import python libs
import os
import sys
import logging
import datetime
import traceback

# Import salt libs
import salt.loader
import salt.minion
import salt.output
import salt.payload
from salt._compat import string_types
from salt.log import LOG_LEVELS

# Custom exceptions
from salt.exceptions import (
    SaltClientError,
    CommandNotFoundError,
    CommandExecutionError,
)

# Import third party libs
import yaml


class Caller(object):
    '''
    Object to wrap the calling of local salt modules for the salt-call command
    '''
    def __init__(self, opts):
        '''
        Pass in the command line options
        '''
        self.opts = opts
        self.opts['caller'] = True
        self.serial = salt.payload.Serial(self.opts)
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
        ret['jid'] = '{0:%Y%m%d%H%M%S%f}'.format(datetime.datetime.now())
        proc_fn = os.path.join(
                salt.minion.get_proc_dir(self.opts['cachedir']),
                ret['jid'])
        if fun not in self.minion.functions:
            sys.stderr.write('Function {0} is not available\n'.format(fun))
            sys.exit(-1)
        try:
            args, kwargs = salt.minion.parse_args_and_kwargs(
                self.minion.functions[fun], self.opts['arg'])
            sdata = {
                    'fun': fun,
                    'pid': os.getpid(),
                    'jid': ret['jid'],
                    'tgt': 'salt-call'}
            with salt.utils.fopen(proc_fn, 'w+') as fp_:
                fp_.write(self.serial.dumps(sdata))
            func = self.minion.functions[fun]
            ret['return'] = func(*args, **kwargs)
            ret['retcode'] = sys.modules[func.__module__].__context__.get(
                    'retcode', 0)
        except (CommandExecutionError) as exc:
            msg = 'Error running \'{0}\': {1}\n'
            active_level = LOG_LEVELS.get(
                self.opts['log_level'].lower(), logging.ERROR)
            if active_level <= logging.DEBUG:
                sys.stderr.write(traceback.format_exc())
            sys.stderr.write(msg.format(fun, str(exc)))
            sys.exit(1)
        except CommandNotFoundError as exc:
            msg = 'Command required for \'{0}\' not found: {1}\n'
            sys.stderr.write(msg.format(fun, str(exc)))
            sys.exit(1)
        try:
            os.remove(proc_fn)
        except (IOError, OSError):
            pass
        if hasattr(self.minion.functions[fun], '__outputter__'):
            oput = self.minion.functions[fun].__outputter__
            if isinstance(oput, string_types):
                ret['out'] = oput
            if oput == 'highstate':
                ret['return'] = {'local': ret['return']}
        if self.opts.get('return', ''):
            ret['id'] = self.opts['id']
            ret['fun'] = fun
            for returner in self.opts['return'].split(','):
                try:
                    self.minion.returners['{0}.returner'.format(returner)](ret)
                except Exception:
                    pass
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
            if name.startswith(self.opts.get('fun', '')):
                print('{0}:\n{1}\n'.format(name, docs[name]))

    def print_grains(self):
        '''
        Print out the grains
        '''
        grains = salt.loader.grains(self.opts)
        salt.output.display_output({'local': grains}, 'grains', self.opts)

    def run(self):
        '''
        Execute the salt call logic
        '''
        ret = self.call()
        out = ret['return']
        # If the type of return is not a dict we wrap the return data
        # This will ensure that --local and local functions will return the
        # same data structure as publish commands.
        if not isinstance(ret['return'], dict):
            out = {'local': ret['return']}
        salt.output.display_output(
                out,
                ret.get('out', 'nested'),
                self.opts)
        if self.opts.get('retcode_passthrough', False):
            sys.exit(ret['retcode'])
