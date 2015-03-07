# -*- coding: utf-8 -*-
'''
The caller module is used as a front-end to manage direct calls to the salt
minion modules.
'''

# Import python libs
from __future__ import print_function
import os
import sys
import logging
import datetime
import traceback

# Import salt libs
import salt.exitcodes
import salt.loader
import salt.minion
import salt.output
import salt.payload
import salt.transport
import salt.utils.args
from salt._compat import string_types
from salt.log import LOG_LEVELS
from salt.utils import print_cli

log = logging.getLogger(__name__)

try:
    from raet import raeting, nacling
    from raet.lane.stacking import LaneStack
    from raet.lane.yarding import RemoteYard

except ImportError:
    # Don't die on missing transport libs since only one transport is required
    pass

# Custom exceptions
from salt.exceptions import (
    SaltClientError,
    CommandNotFoundError,
    CommandExecutionError,
    SaltInvocationError,
)


class Caller(object):
    '''
    Factory class to create salt-call callers for different transport
    '''
    @staticmethod
    def factory(opts, **kwargs):
        # Default to ZeroMQ for now
        ttype = 'zeromq'

        # determine the ttype
        if 'transport' in opts:
            ttype = opts['transport']
        elif 'transport' in opts.get('pillar', {}).get('master', {}):
            ttype = opts['pillar']['master']['transport']

        # switch on available ttypes
        if ttype == 'zeromq':
            return ZeroMQCaller(opts, **kwargs)
        elif ttype == 'raet':
            return RAETCaller(opts, **kwargs)
        else:
            raise Exception('Callers are only defined for ZeroMQ and raet')
            # return NewKindOfCaller(opts, **kwargs)


class ZeroMQCaller(object):
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
        # raet channel here
        ret = {}
        fun = self.opts['fun']
        ret['jid'] = '{0:%Y%m%d%H%M%S%f}'.format(datetime.datetime.now())
        proc_fn = os.path.join(
            salt.minion.get_proc_dir(self.opts['cachedir']),
            ret['jid']
        )
        if fun not in self.minion.functions:
            sys.stderr.write('Function {0} is not available\n'.format(fun))
            sys.exit(-1)
        try:
            sdata = {
                'fun': fun,
                'pid': os.getpid(),
                'jid': ret['jid'],
                'tgt': 'salt-call'}
            args, kwargs = salt.minion.load_args_and_kwargs(
                self.minion.functions[fun],
                salt.utils.args.parse_input(self.opts['arg']),
                data=sdata)
            try:
                with salt.utils.fopen(proc_fn, 'w+b') as fp_:
                    fp_.write(self.serial.dumps(sdata))
            except NameError:
                # Don't require msgpack with local
                pass
            except IOError:
                sys.stderr.write(
                    'Cannot write to process directory. '
                    'Do you have permissions to '
                    'write to {0} ?\n'.format(proc_fn))
            func = self.minion.functions[fun]
            try:
                ret['return'] = func(*args, **kwargs)
            except TypeError as exc:
                trace = traceback.format_exc()
                sys.stderr.write('Passed invalid arguments: {0}\n'.format(exc))
                active_level = LOG_LEVELS.get(
                    self.opts['log_level'].lower(), logging.ERROR)
                if active_level <= logging.DEBUG:
                    sys.stderr.write(trace)
                sys.exit(salt.exitcodes.EX_GENERIC)
            try:
                ret['retcode'] = sys.modules[
                    func.__module__].__context__.get('retcode', 0)
            except AttributeError:
                ret['retcode'] = 1
        except (CommandExecutionError) as exc:
            msg = 'Error running \'{0}\': {1}\n'
            active_level = LOG_LEVELS.get(
                self.opts['log_level'].lower(), logging.ERROR)
            if active_level <= logging.DEBUG:
                sys.stderr.write(traceback.format_exc())
            sys.stderr.write(msg.format(fun, str(exc)))
            sys.exit(salt.exitcodes.EX_GENERIC)
        except CommandNotFoundError as exc:
            msg = 'Command required for \'{0}\' not found: {1}\n'
            sys.stderr.write(msg.format(fun, str(exc)))
            sys.exit(salt.exitcodes.EX_GENERIC)
        try:
            os.remove(proc_fn)
        except (IOError, OSError):
            pass
        if hasattr(self.minion.functions[fun], '__outputter__'):
            oput = self.minion.functions[fun].__outputter__
            if isinstance(oput, string_types):
                ret['out'] = oput
        is_local = self.opts['local'] or self.opts.get(
            'file_client', False) == 'local'
        returners = self.opts.get('return', '').split(',')
        if (not is_local) or returners:
            ret['id'] = self.opts['id']
            ret['fun'] = fun
            ret['fun_args'] = self.opts['arg']

        for returner in returners:
            if not returner:  # if we got an empty returner somehow, skip
                continue
            try:
                ret['success'] = True
                self.minion.returners['{0}.returner'.format(returner)](ret)
            except Exception:
                pass

        # return the job infos back up to the respective minion's master

        if not is_local:
            try:
                mret = ret.copy()
                mret['jid'] = 'req'
                self.return_pub(mret)
            except Exception:
                pass
        # close raet channel here
        return ret

    def return_pub(self, ret):
        '''
        Return the data up to the master
        '''
        channel = salt.transport.Channel.factory(self.opts, usage='salt_call')
        load = {'cmd': '_return', 'id': self.opts['id']}
        for key, value in ret.items():
            load[key] = value
        channel.send(load)

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
                print_cli('{0}:\n{1}\n'.format(name, docs[name]))

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
        try:
            ret = self.call()
            out = ret.get('out', 'nested')
            if self.opts['metadata']:
                print_ret = ret
                out = 'nested'
            else:
                print_ret = ret.get('return', {})
            salt.output.display_output(
                    {'local': print_ret},
                    out,
                    self.opts)
            if self.opts.get('retcode_passthrough', False):
                sys.exit(ret['retcode'])
        except SaltInvocationError as err:
            raise SystemExit(err)


class RAETCaller(ZeroMQCaller):
    '''
    Object to wrap the calling of local salt modules for the salt-call command
    when transport is raet
    '''
    def __init__(self, opts):
        '''
        Pass in the command line options
        '''
        self.stack = self._setup_caller_stack(opts)
        salt.transport.jobber_stack = self.stack

        super(RAETCaller, self).__init__(opts)

    def run(self):
        '''
        Execute the salt call logic
        '''
        try:
            ret = self.call()
            self.stack.server.close()
            salt.transport.jobber_stack = None

            if self.opts['metadata']:
                print_ret = ret
            else:
                print_ret = ret.get('return', {})
            salt.output.display_output(
                    {'local': print_ret},
                    ret.get('out', 'nested'),
                    self.opts)
            if self.opts.get('retcode_passthrough', False):
                sys.exit(ret['retcode'])
        except SaltInvocationError as err:
            raise SystemExit(err)

    def _setup_caller_stack(self, opts):
        '''
        Setup and return the LaneStack and Yard used by by channel when global
        not already setup such as in salt-call to communicate to-from the minion

        '''
        mid = opts['id']
        sockdirpath = opts['sock_dir']
        uid = nacling.uuid(size=18)
        name = 'caller' + uid
        stack = LaneStack(name=name,
                          lanename=mid,
                          sockdirpath=sockdirpath)

        stack.Pk = raeting.packKinds.pack
        stack.addRemote(RemoteYard(stack=stack,
                                   name='manor',
                                   lanename=mid,
                                   dirpath=sockdirpath))
        log.debug("Created Caller Jobber Stack {0}\n".format(stack.name))
        return stack
