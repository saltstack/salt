# -*- coding: utf-8 -*-
'''
The caller module is used as a front-end to manage direct calls to the salt
minion modules.
'''

# Import python libs
from __future__ import absolute_import, print_function

import os
import sys
import time
import logging
import traceback

# Import salt libs
import salt
import salt.loader
import salt.minion
import salt.output
import salt.payload
import salt.transport
import salt.utils.args
import salt.utils.jid
import salt.utils.minion
import salt.defaults.exitcodes
from salt.log import LOG_LEVELS
from salt.utils import is_windows
from salt.utils import print_cli
from salt.utils import kinds
from salt.utils import activate_profile
from salt.utils import output_profile
from salt.utils.process import MultiprocessingProcess
from salt.cli import daemons

try:
    from raet import raeting, nacling
    from raet.lane.stacking import LaneStack
    from raet.lane.yarding import RemoteYard, Yard

    if is_windows():
        import win32file

except ImportError:
    # Don't die on missing transport libs since only one transport is required
    pass

# Import 3rd-party libs
import salt.ext.six as six

# Custom exceptions
from salt.exceptions import (
    SaltClientError,
    CommandNotFoundError,
    CommandExecutionError,
    SaltInvocationError,
)

log = logging.getLogger(__name__)


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
        if ttype in ('zeromq', 'tcp'):
            return ZeroMQCaller(opts, **kwargs)
        elif ttype == 'raet':
            return RAETCaller(opts, **kwargs)
        else:
            raise Exception('Callers are only defined for ZeroMQ and raet')
            # return NewKindOfCaller(opts, **kwargs)


class BaseCaller(object):
    '''
    Base class for caller transports
    '''
    def __init__(self, opts):
        '''
        Pass in command line opts
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

    def print_docs(self):
        '''
        Pick up the documentation for all of the modules and print it out.
        '''
        docs = {}
        for name, func in six.iteritems(self.minion.functions):
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
        profiling_enabled = self.opts.get('profiling_enabled', False)
        try:
            pr = activate_profile(profiling_enabled)
            try:
                ret = self.call()
            finally:
                output_profile(pr,
                               stats_path=self.opts.get('profiling_path',
                                                        '/tmp/stats'),
                               stop=True)
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

    def call(self):
        '''
        Call the module
        '''
        ret = {}
        fun = self.opts['fun']
        ret['jid'] = salt.utils.jid.gen_jid()
        proc_fn = os.path.join(
            salt.minion.get_proc_dir(self.opts['cachedir']),
            ret['jid']
        )
        if fun not in self.minion.functions:
            sys.stderr.write(self.minion.functions.missing_fun_string(fun))
            mod_name = fun.split('.')[0]
            if mod_name in self.minion.function_errors:
                sys.stderr.write(' Possible reasons: {0}\n'.format(self.minion.function_errors[mod_name]))
            else:
                sys.stderr.write('\n')
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
                sys.stderr.write('\nPassed invalid arguments: {0}.\n\nUsage:\n'.format(exc))
                print_cli(func.__doc__)
                active_level = LOG_LEVELS.get(
                    self.opts['log_level'].lower(), logging.ERROR)
                if active_level <= logging.DEBUG:
                    trace = traceback.format_exc()
                    sys.stderr.write(trace)
                sys.exit(salt.defaults.exitcodes.EX_GENERIC)
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
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        except CommandNotFoundError as exc:
            msg = 'Command required for \'{0}\' not found: {1}\n'
            sys.stderr.write(msg.format(fun, str(exc)))
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        try:
            os.remove(proc_fn)
        except (IOError, OSError):
            pass
        if hasattr(self.minion.functions[fun], '__outputter__'):
            oput = self.minion.functions[fun].__outputter__
            if isinstance(oput, six.string_types):
                ret['out'] = oput
        is_local = self.opts['local'] or self.opts.get(
            'file_client', False) == 'local' or self.opts.get(
            'master_type') == 'disable'
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
        elif self.opts['cache_jobs']:
            # Local job cache has been enabled
            salt.utils.minion.cache_jobs(self.opts, ret['jid'], ret)

        # close raet channel here
        return ret


class ZeroMQCaller(BaseCaller):
    '''
    Object to wrap the calling of local salt modules for the salt-call command
    '''
    def __init__(self, opts):
        '''
        Pass in the command line options
        '''
        super(ZeroMQCaller, self).__init__(opts)

    def return_pub(self, ret):
        '''
        Return the data up to the master
        '''
        channel = salt.transport.Channel.factory(self.opts, usage='salt_call')
        load = {'cmd': '_return', 'id': self.opts['id']}
        for key, value in six.iteritems(ret):
            load[key] = value
        channel.send(load)


def raet_minion_run(cleanup_protecteds):
    '''
    Set up the minion caller. Should be run in its own process.
    This function is intentionally left out of RAETCaller. This will avoid
    needing to pickle the RAETCaller object on Windows.
    '''
    minion = daemons.Minion()  # daemonizes here
    minion.call(cleanup_protecteds=cleanup_protecteds)  # caller minion.call_in uses caller.flo


class RAETCaller(BaseCaller):
    '''
    Object to wrap the calling of local salt modules for the salt-call command
    when transport is raet

    There are two operation modes.
    1) Use a preexisting minion
    2) Set up a special caller minion if no preexisting minion
        The special caller minion is a subset whose only function is to perform
        Salt-calls with raet as the transport
        The essentials:
            A RoadStack whose local estate name is of the form "role_kind" where:
               role is the minion id opts['id']
               kind is opts['__role'] which should be 'caller' APPL_KIND_NAMES
               The RoadStack if for communication to/from a master

            A LaneStack with manor yard so that RaetChannels created by the func Jobbers
            can communicate through this manor yard then through the
            RoadStack to/from a master

            A Router to route between the stacks (Road and Lane)

            These are all managed via a FloScript named caller.flo

    '''
    def __init__(self, opts):
        '''
        Pass in the command line options
        '''
        self.process = None
        if not opts['local']:
            self.stack = self._setup_caller_stack(opts)
            salt.transport.jobber_stack = self.stack

            if (opts.get('__role') ==
                    kinds.APPL_KIND_NAMES[kinds.applKinds.caller]):
                # spin up and fork minion here
                self.process = MultiprocessingProcess(target=raet_minion_run,
                                    kwargs={'cleanup_protecteds': [self.stack.ha], })
                self.process.start()
                # wait here until '/var/run/salt/minion/alpha_caller.manor.uxd' exists
                self._wait_caller(opts)

        super(RAETCaller, self).__init__(opts)

    def run(self):
        '''
        Execute the salt call logic
        '''
        try:
            ret = self.call()
            if not self.opts['local']:
                self.stack.server.close()
                salt.transport.jobber_stack = None

            if self.opts['metadata']:
                print_ret = ret
            else:
                print_ret = ret.get('return', {})
            if self.process:
                self.process.terminate()
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
        role = opts.get('id')
        if not role:
            emsg = ("Missing role required to setup RAETChannel.")
            log.error(emsg + "\n")
            raise ValueError(emsg)

        kind = opts.get('__role')  # application kind 'master', 'minion', etc
        if kind not in kinds.APPL_KINDS:
            emsg = ("Invalid application kind = '{0}' for RAETChannel.".format(kind))
            log.error(emsg + "\n")
            raise ValueError(emsg)
        if kind in [kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                    kinds.APPL_KIND_NAMES[kinds.applKinds.caller], ]:
            lanename = "{0}_{1}".format(role, kind)
        else:
            emsg = ("Unsupported application kind '{0}' for RAETChannel.".format(kind))
            log.error(emsg + '\n')
            raise ValueError(emsg)

        sockdirpath = opts['sock_dir']
        stackname = 'caller' + nacling.uuid(size=18)
        stack = LaneStack(name=stackname,
                          lanename=lanename,
                          sockdirpath=sockdirpath)

        stack.Pk = raeting.PackKind.pack.value
        stack.addRemote(RemoteYard(stack=stack,
                                   name='manor',
                                   lanename=lanename,
                                   dirpath=sockdirpath))
        log.debug("Created Caller Jobber Stack {0}\n".format(stack.name))

        return stack

    def _wait_caller(self, opts):
        '''
        Returns when RAET Minion Yard is available
        '''
        yardname = 'manor'
        dirpath = opts['sock_dir']

        role = opts.get('id')
        if not role:
            emsg = ("Missing role required to setup RAET SaltCaller.")
            log.error(emsg + "\n")
            raise ValueError(emsg)

        kind = opts.get('__role')  # application kind 'master', 'minion', etc
        if kind not in kinds.APPL_KINDS:
            emsg = ("Invalid application kind = '{0}' for RAET SaltCaller.".format(kind))
            log.error(emsg + "\n")
            raise ValueError(emsg)

        if kind in [kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                    kinds.APPL_KIND_NAMES[kinds.applKinds.caller], ]:
            lanename = "{0}_{1}".format(role, kind)
        else:
            emsg = ("Unsupported application kind '{0}' for RAET SaltCaller.".format(kind))
            log.error(emsg + '\n')
            raise ValueError(emsg)

        ha, dirpath = Yard.computeHa(dirpath, lanename, yardname)

        if is_windows():
            # RAET lanes do not use files on Windows. Need to use win32file
            # API to check for existence.
            exists = False
            while not exists:
                try:
                    f = win32file.CreateFile(
                            ha,
                            win32file.GENERIC_WRITE | win32file.GENERIC_READ,
                            win32file.FILE_SHARE_READ,
                            None,
                            win32file.OPEN_EXISTING,
                            0,
                            None)
                    win32file.CloseHandle(f)
                    exists = True
                except win32file.error:
                    time.sleep(0.1)
        else:
            while not ((os.path.exists(ha) and
                        not os.path.isfile(ha) and
                        not os.path.isdir(ha))):
                time.sleep(0.1)
        time.sleep(0.5)
