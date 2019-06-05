# -*- coding: utf-8 -*-
'''
Jobber Behaviors
'''
# pylint: disable=W0232
# pylint: disable=3rd-party-module-not-gated

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import types
import logging
import traceback
import multiprocessing
import subprocess

# Import salt libs
from salt.ext import six
import salt.daemons.masterapi
import salt.utils.args
import salt.utils.data
import salt.utils.files
import salt.utils.json
import salt.utils.kinds as kinds
import salt.utils.process
import salt.utils.stringutils
import salt.transport
from raet import raeting, nacling
from raet.lane.stacking import LaneStack
from raet.lane.yarding import RemoteYard

from salt.utils.platform import is_windows
from salt.utils.event import tagify

from salt.exceptions import (
        CommandExecutionError, CommandNotFoundError, SaltInvocationError)

# Import ioflo libs
import ioflo.base.deeding

from ioflo.base.consoling import getConsole
console = getConsole()
log = logging.getLogger(__name__)


@ioflo.base.deeding.deedify(
        salt.utils.stringutils.to_str('SaltRaetShellJobberCheck'),
        ioinits={'opts': salt.utils.stringutils.to_str('.salt.opts'),
                 'grains': salt.utils.stringutils.to_str('.salt.grains'),
                 'fun': salt.utils.stringutils.to_str('.salt.var.fun'),
                 'matcher': salt.utils.stringutils.to_str('.salt.matcher'),
                 'shells': salt.utils.stringutils.to_str('.salt.var.shells'),
                 'stack': salt.utils.stringutils.to_str('.salt.road.manor.stack')})
def jobber_check(self):
    '''
    Iterate over the shell jobbers and return the ones that have finished
    '''
    rms = []
    for jid in self.shells.value:
        if isinstance(self.shells.value[jid]['proc'].poll(), int):
            rms.append(jid)
            data = self.shells.value[jid]
            stdout, stderr = data['proc'].communicate()
            ret = salt.utils.json.loads(
                stdout,
                object_hook=salt.utils.data.encode_dict if six.PY2 else None
            )['local']
            route = {'src': (self.stack.value.local.name, 'manor', 'jid_ret'),
                     'dst': (data['msg']['route']['src'][0], None, 'remote_cmd')}
            ret['cmd'] = '_return'
            ret['id'] = self.opts.value['id']
            ret['jid'] = jid
            msg = {'route': route, 'load': ret}
            master = self.stack.value.nameRemotes.get(data['msg']['route']['src'][0])
            self.stack.value.message(
                    msg,
                    master.uid)
    for rm_ in rms:
        self.shells.value.pop(rm_)


@ioflo.base.deeding.deedify(
        salt.utils.stringutils.to_str('SaltRaetShellJobber'),
        ioinits={'opts': salt.utils.stringutils.to_str('.salt.opts'),
                 'grains': salt.utils.stringutils.to_str('.salt.grains'),
                 'fun': salt.utils.stringutils.to_str('.salt.var.fun'),
                 'matcher': salt.utils.stringutils.to_str('.salt.matcher'),
                 'modules': salt.utils.stringutils.to_str('.salt.loader.modules'),
                 'shells': {'ipath': salt.utils.stringutils.to_str('.salt.var.shells'),
                            'ival': {}}})
def shell_jobber(self):
    '''
    Shell jobber start!
    '''
    while self.fun.value:
        msg = self.fun.value.popleft()
        data = msg.get('pub')
        match = getattr(
                self.matcher.value,
                '{0}_match'.format(
                    data.get('tgt_type', 'glob')
                    )
                )(data['tgt'])
        if not match:
            continue
        fun = data['fun']
        if fun in self.modules.value:
            func = self.modules.value[fun]
        else:
            continue
        args, kwargs = salt.minion.load_args_and_kwargs(
            func,
            salt.utils.args.parse_input(
                data['arg'],
                no_parse=data.get('no_parse', [])),
            data)
        cmd = ['salt-call',
               '--out', 'json',
               '--metadata',
               '-c', salt.syspaths.CONFIG_DIR]
        if 'return' in data:
            cmd.append('--return')
            cmd.append(data['return'])
        cmd.append(fun)
        for arg in args:
            cmd.append(arg)
        for key in kwargs:
            cmd.append('{0}={1}'.format(key, kwargs[key]))
        que = {'pub': data,
               'msg': msg}
        que['proc'] = subprocess.Popen(
                cmd,
                shell=False,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE)
        self.shells.value[data['jid']] = que


class SaltRaetNixJobber(ioflo.base.deeding.Deed):
    '''
    Execute a function call job on a minion on a *nix based system
    FloScript:

    do salt raet nix jobber

    '''
    Ioinits = {'opts_store': salt.utils.stringutils.to_str('.salt.opts'),
               'grains': salt.utils.stringutils.to_str('.salt.grains'),
               'modules': salt.utils.stringutils.to_str('.salt.loader.modules'),
               'returners': salt.utils.stringutils.to_str('.salt.loader.returners'),
               'module_executors': salt.utils.stringutils.to_str('.salt.loader.executors'),
               'fun': salt.utils.stringutils.to_str('.salt.var.fun'),
               'matcher': salt.utils.stringutils.to_str('.salt.matcher'),
               'executors': salt.utils.stringutils.to_str('.salt.track.executors'),
               'road_stack': salt.utils.stringutils.to_str('.salt.road.manor.stack'), }

    def _prepare(self):
        '''
        Map opts for convenience
        '''
        self.opts = self.opts_store.value
        self.proc_dir = salt.minion.get_proc_dir(self.opts['cachedir'])
        self.serial = salt.payload.Serial(self.opts)
        self.executors.value = {}

    def _setup_jobber_stack(self):
        '''
        Setup and return the LaneStack and Yard used by the jobber yard
        to communicate with the minion manor yard

        '''
        role = self.opts.get('id', '')
        if not role:
            emsg = ("Missing role required to setup Jobber Lane.")
            log.error(emsg + "\n")
            raise ValueError(emsg)

        kind = self.opts['__role']
        if kind not in kinds.APPL_KINDS:
            emsg = ("Invalid application kind = '{0}' for Jobber lane.".format(kind))
            log.error(emsg + "\n")
            raise ValueError(emsg)

        if kind == 'minion':
            lanename = "{0}_{1}".format(role, kind)
        else:
            emsg = ("Unsupported application kind = '{0}' for Jobber Lane.".format(kind))
            log.error(emsg + '\n')
            raise ValueError(emsg)

        sockdirpath = self.opts['sock_dir']
        name = 'jobber' + nacling.uuid(size=18)
        stack = LaneStack(
                name=name,
                lanename=lanename,
                sockdirpath=sockdirpath)

        stack.Pk = raeting.PackKind.pack.value
        # add remote for the manor yard
        stack.addRemote(RemoteYard(stack=stack,
                                   name='manor',
                                   lanename=lanename,
                                   dirpath=sockdirpath))
        console.concise("Created Jobber Stack {0}\n".format(stack.name))
        return stack

    def _return_pub(self, msg, ret, stack):
        '''
        Send the return data back via the uxd socket
        '''
        route = {'src': (self.road_stack.value.local.name, stack.local.name, 'jid_ret'),
                 'dst': (msg['route']['src'][0], None, 'remote_cmd')}
        mid = self.opts['id']
        ret['cmd'] = '_return'
        ret['id'] = mid
        try:
            oput = self.modules.value[ret['fun']].__outputter__
        except (KeyError, AttributeError, TypeError):
            pass
        else:
            if isinstance(oput, six.string_types):
                ret['out'] = oput
        msg = {'route': route, 'load': ret}
        stack.transmit(msg, stack.fetchUidByName('manor'))
        stack.serviceAll()

    def action(self):
        '''
        Pull the queue for functions to execute
        '''
        while self.fun.value:
            msg = self.fun.value.popleft()
            data = msg.get('pub')
            match = getattr(
                    self.matcher.value,
                    '{0}_match'.format(
                        data.get('tgt_type', 'glob')
                        )
                    )(data['tgt'])
            if not match:
                continue
            if 'user' in data:
                log.info(
                    'User %s Executing command %s with jid %s',
                    data['user'], data['fun'], data['jid']
                )
            else:
                log.info(
                    'Executing command %s with jid %s',
                    data['fun'], data['jid']
                )
            log.debug('Command details %s', data)

            if is_windows():
                # SaltRaetNixJobber is not picklable. Pickling is necessary
                # when spawning a process in Windows. Since the process will
                # be spawned and joined on non-Windows platforms, instead of
                # this, just run the function directly and absorb any thrown
                # exceptions.
                try:
                    self.proc_run(msg)
                except Exception as exc:
                    log.error('Exception caught by jobber: %s', exc, exc_info=True)
            else:
                process = multiprocessing.Process(
                        target=self.proc_run,
                        kwargs={'msg': msg}
                        )
                process.start()
                process.join()

    def proc_run(self, msg):
        '''
        Execute the run in a dedicated process
        '''
        data = msg['pub']
        fn_ = os.path.join(self.proc_dir, data['jid'])
        self.opts['__ex_id'] = data['jid']
        salt.utils.process.daemonize_if(self.opts)

        salt.transport.jobber_stack = stack = self._setup_jobber_stack()
        # set up return destination from source
        src_estate, src_yard, src_share = msg['route']['src']
        salt.transport.jobber_estate_name = src_estate
        salt.transport.jobber_yard_name = src_yard

        sdata = {'pid': os.getpid()}
        sdata.update(data)
        with salt.utils.files.fopen(fn_, 'w+b') as fp_:
            fp_.write(self.serial.dumps(sdata))
        ret = {'success': False}
        function_name = data['fun']
        if function_name in self.modules.value:
            try:
                func = self.modules.value[data['fun']]
                args, kwargs = salt.minion.load_args_and_kwargs(
                    func,
                    salt.utils.args.parse_input(
                        data['arg'],
                        no_parse=data.get('no_parse', [])),
                    data)
                sys.modules[func.__module__].__context__['retcode'] = 0

                executors = data.get('module_executors') or self.opts.get('module_executors', ['direct_call'])
                if isinstance(executors, six.string_types):
                    executors = [executors]
                elif not isinstance(executors, list) or not executors:
                    raise SaltInvocationError(
                        'Wrong executors specification: {0}. String or '
                        'non-empty list expected'.format(executors)
                    )
                if self.opts.get('sudo_user', '') and executors[-1] != 'sudo':
                    executors[-1] = 'sudo'  # replace
                log.trace("Executors list %s", executors)

                for name in executors:
                    fname = '{0}.execute'.format(name)
                    if fname not in self.module_executors.value:
                        raise SaltInvocationError("Executor '{0}' is not available".format(name))
                    return_data = self.module_executors.value[fname](self.opts, data, func, args, kwargs)
                    if return_data is not None:
                        break

                if isinstance(return_data, types.GeneratorType):
                    ind = 0
                    iret = {}
                    for single in return_data:
                        if isinstance(single, dict) and isinstance(iret, list):
                            iret.update(single)
                        else:
                            if not iret:
                                iret = []
                            iret.append(single)
                        tag = tagify(
                                [data['jid'], 'prog', self.opts['id'], six.text_type(ind)],
                                'job')
                        event_data = {'return': single}
                        self._fire_master(event_data, tag)  # Need to look into this
                        ind += 1
                    ret['return'] = iret
                else:
                    ret['return'] = return_data
                ret['retcode'] = sys.modules[func.__module__].__context__.get(
                    'retcode',
                    0
                )
                ret['success'] = True
            except CommandNotFoundError as exc:
                msg = 'Command required for \'{0}\' not found'.format(
                    function_name
                )
                log.debug(msg, exc_info=True)
                ret['return'] = '{0}: {1}'.format(msg, exc)
            except CommandExecutionError as exc:
                log.error(
                    'A command in \'%s\' had a problem: %s',
                    function_name, exc,
                    exc_info_on_loglevel=logging.DEBUG
                )
                ret['return'] = 'ERROR: {0}'.format(exc)
            except SaltInvocationError as exc:
                log.error(
                    'Problem executing \'%s\': %s',
                    function_name, exc,
                    exc_info_on_loglevel=logging.DEBUG
                )
                ret['return'] = 'ERROR executing \'{0}\': {1}'.format(
                    function_name, exc
                )
            except TypeError as exc:
                msg = ('TypeError encountered executing {0}: {1}. See '
                       'debug log for more info.').format(function_name, exc)
                log.warning(msg, exc_info_on_loglevel=logging.DEBUG)
                ret['return'] = msg
            except Exception:
                msg = 'The minion function caused an exception'
                log.warning(msg, exc_info_on_loglevel=logging.DEBUG)
                ret['return'] = '{0}: {1}'.format(msg, traceback.format_exc())
        else:
            ret['return'] = '\'{0}\' is not available.'.format(function_name)

        ret['jid'] = data['jid']
        ret['fun'] = data['fun']
        ret['fun_args'] = data['arg']
        self._return_pub(msg, ret, stack)
        if data['ret']:
            ret['id'] = self.opts['id']
            for returner in set(data['ret'].split(',')):
                try:
                    self.returners.value['{0}.returner'.format(
                        returner
                    )](ret)
                except Exception as exc:
                    log.error('The return failed for job %s %s', data['jid'], exc)
        console.concise("Closing Jobber Stack {0}\n".format(stack.name))
        stack.server.close()
        salt.transport.jobber_stack = None
