# -*- coding: utf-8 -*-
'''
The caller module is used as a front-end to manage direct calls to the salt
minion modules.
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os
import sys
import logging
import traceback

# Import salt libs
import salt
import salt.loader
import salt.minion
import salt.output
import salt.payload
import salt.transport
import salt.transport.client
import salt.utils.args
import salt.utils.files
import salt.utils.jid
import salt.utils.minion
import salt.utils.profile
import salt.utils.stringutils
import salt.defaults.exitcodes
from salt.log import LOG_LEVELS

# Import 3rd-party libs
from salt.ext import six

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
        if ttype in ('zeromq', 'tcp', 'detect'):
            return ZeroMQCaller(opts, **kwargs)
        else:
            raise Exception('Callers are only defined for ZeroMQ and TCP')
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
            if self.opts.get('proxyid'):
                self.minion = salt.minion.SProxyMinion(opts)
            else:
                self.minion = salt.minion.SMinion(opts)
        except SaltClientError as exc:
            raise SystemExit(six.text_type(exc))

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
                salt.utils.stringutils.print_cli('{0}:\n{1}\n'.format(name, docs[name]))

    def print_grains(self):
        '''
        Print out the grains
        '''
        grains = self.minion.opts.get('grains') or salt.loader.grains(self.opts)
        salt.output.display_output({'local': grains}, 'grains', self.opts)

    def run(self):
        '''
        Execute the salt call logic
        '''
        profiling_enabled = self.opts.get('profiling_enabled', False)
        try:
            pr = salt.utils.profile.activate_profile(profiling_enabled)
            try:
                ret = self.call()
            finally:
                salt.utils.profile.output_profile(
                    pr,
                    stats_path=self.opts.get('profiling_path', '/tmp/stats'),
                    stop=True)
            out = ret.get('out', 'nested')
            if self.opts['print_metadata']:
                print_ret = ret
                out = 'nested'
            else:
                print_ret = ret.get('return', {})
            salt.output.display_output(
                    {'local': print_ret},
                    out=out,
                    opts=self.opts,
                    _retcode=ret.get('retcode', 0))
            # _retcode will be available in the kwargs of the outputter function
            if self.opts.get('retcode_passthrough', False):
                sys.exit(ret['retcode'])
            elif ret['retcode'] != salt.defaults.exitcodes.EX_OK:
                sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        except SaltInvocationError as err:
            raise SystemExit(err)

    def call(self):
        '''
        Call the module
        '''
        ret = {}
        fun = self.opts['fun']
        ret['jid'] = salt.utils.jid.gen_jid(self.opts)
        proc_fn = os.path.join(
            salt.minion.get_proc_dir(self.opts['cachedir']),
            ret['jid']
        )
        if fun not in self.minion.functions:
            docs = self.minion.functions['sys.doc']('{0}*'.format(fun))
            if docs:
                docs[fun] = self.minion.functions.missing_fun_string(fun)
                ret['out'] = 'nested'
                ret['return'] = docs
                return ret
            sys.stderr.write(self.minion.functions.missing_fun_string(fun))
            mod_name = fun.split('.')[0]
            if mod_name in self.minion.function_errors:
                sys.stderr.write(' Possible reasons: {0}\n'.format(self.minion.function_errors[mod_name]))
            else:
                sys.stderr.write('\n')
            sys.exit(-1)
        metadata = self.opts.get('metadata')
        if metadata is not None:
            metadata = salt.utils.args.yamlify_arg(metadata)
        try:
            sdata = {
                'fun': fun,
                'pid': os.getpid(),
                'jid': ret['jid'],
                'tgt': 'salt-call'}
            if metadata is not None:
                sdata['metadata'] = metadata
            args, kwargs = salt.minion.load_args_and_kwargs(
                self.minion.functions[fun],
                salt.utils.args.parse_input(
                    self.opts['arg'],
                    no_parse=self.opts.get('no_parse', [])),
                data=sdata)
            try:
                with salt.utils.files.fopen(proc_fn, 'w+b') as fp_:
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
            data = {
              'arg': args,
              'fun': fun
            }
            data.update(kwargs)
            executors = getattr(self.minion, 'module_executors', []) or \
                        salt.utils.args.yamlify_arg(
                            self.opts.get('module_executors', '[direct_call]')
                        )
            if self.opts.get('executor_opts', None):
                data['executor_opts'] = salt.utils.args.yamlify_arg(
                    self.opts['executor_opts']
                )
            if isinstance(executors, six.string_types):
                executors = [executors]
            try:
                for name in executors:
                    fname = '{0}.execute'.format(name)
                    if fname not in self.minion.executors:
                        raise SaltInvocationError("Executor '{0}' is not available".format(name))
                    ret['return'] = self.minion.executors[fname](self.opts, data, func, args, kwargs)
                    if ret['return'] is not None:
                        break
            except TypeError as exc:
                sys.stderr.write('\nPassed invalid arguments: {0}.\n\nUsage:\n'.format(exc))
                salt.utils.stringutils.print_cli(func.__doc__)
                active_level = LOG_LEVELS.get(
                    self.opts['log_level'].lower(), logging.ERROR)
                if active_level <= logging.DEBUG:
                    trace = traceback.format_exc()
                    sys.stderr.write(trace)
                sys.exit(salt.defaults.exitcodes.EX_GENERIC)
            try:
                retcode = sys.modules[
                    func.__module__].__context__.get('retcode', 0)
            except AttributeError:
                retcode = salt.defaults.exitcodes.EX_GENERIC

            if retcode == 0:
                # No nonzero retcode in __context__ dunder. Check if return
                # is a dictionary with a "result" or "success" key.
                try:
                    func_result = all(ret['return'].get(x, True)
                                      for x in ('result', 'success'))
                except Exception:
                    # return data is not a dict
                    func_result = True
                if not func_result:
                    retcode = salt.defaults.exitcodes.EX_GENERIC

            ret['retcode'] = retcode
        except (CommandExecutionError) as exc:
            msg = 'Error running \'{0}\': {1}\n'
            active_level = LOG_LEVELS.get(
                self.opts['log_level'].lower(), logging.ERROR)
            if active_level <= logging.DEBUG:
                sys.stderr.write(traceback.format_exc())
            sys.stderr.write(msg.format(fun, exc))
            sys.exit(salt.defaults.exitcodes.EX_GENERIC)
        except CommandNotFoundError as exc:
            msg = 'Command required for \'{0}\' not found: {1}\n'
            sys.stderr.write(msg.format(fun, exc))
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
            if metadata is not None:
                ret['metadata'] = metadata

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
        channel = salt.transport.client.ReqChannel.factory(self.opts, usage='salt_call')
        load = {'cmd': '_return', 'id': self.opts['id']}
        for key, value in six.iteritems(ret):
            load[key] = value
        try:
            channel.send(load)
        finally:
            channel.close()
