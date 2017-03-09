# -*- coding: utf-8 -*-
'''
Jobber Behaviors
'''
# pylint: disable=W0232
# pylint: disable=3rd-party-module-not-gated

# Import python libs
from __future__ import absolute_import
import os
import sys
import types
import logging
import traceback
import multiprocessing
import subprocess
import json

# Import salt libs
import salt.ext.six as six
import salt.daemons.masterapi
import salt.utils.args
import salt.utils
import salt.transport
from raet import raeting, nacling
from raet.lane.stacking import LaneStack
from raet.lane.yarding import RemoteYard

from salt.executors import FUNCTION_EXECUTORS
from salt.utils import kinds, is_windows
from salt.utils.event import tagify

from salt.exceptions import (
        CommandExecutionError, CommandNotFoundError, SaltInvocationError)

# Import ioflo libs
import ioflo.base.deeding

from ioflo.base.consoling import getConsole
console = getConsole()
log = logging.getLogger(__name__)


@ioflo.base.deeding.deedify(
        'SaltRaetShellJobberCheck',
        ioinits={'opts': '.salt.opts',
                 'grains': '.salt.grains',
                 'fun': '.salt.var.fun',
                 'matcher': '.salt.matcher',
                 'shells': '.salt.var.shells',
                 'stack': '.salt.road.manor.stack'})
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
            ret = json.loads(salt.utils.to_str(stdout), object_hook=salt.utils.decode_dict)['local']
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
        'SaltRaetShellJobber',
        ioinits={'opts': '.salt.opts',
                 'grains': '.salt.grains',
                 'fun': '.salt.var.fun',
                 'matcher': '.salt.matcher',
                 'modules': '.salt.loader.modules',
                 'shells': {'ipath': '.salt.var.shells', 'ival': {}}})
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
            salt.utils.args.parse_input(data['arg']),
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
    Ioinits = {'opts_store': '.salt.opts',
               'grains': '.salt.grains',
               'modules': '.salt.loader.modules',
               'returners': '.salt.loader.returners',
               'module_executors': '.salt.loader.executors',
               'fun': '.salt.var.fun',
               'matcher': '.salt.matcher',
               'executors': '.salt.track.executors',
               'road_stack': '.salt.road.manor.stack', }

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
            if isinstance(oput, str):
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
                        'User {0[user]} Executing command {0[fun]} with jid '
                        '{0[jid]}'.format(data))
            else:
                log.info(
                        'Executing command {0[fun]} with jid {0[jid]}'.format(data)
                        )
            log.debug('Command details {0}'.format(data))

            if is_windows():
                # SaltRaetNixJobber is not picklable. Pickling is necessary
                # when spawning a process in Windows. Since the process will
                # be spawned and joined on non-Windows platforms, instead of
                # this, just run the function directly and absorb any thrown
                # exceptions.
                try:
                    self.proc_run(msg)
                except Exception as exc:
                    log.error(
                            'Exception caught by jobber: {0}'.format(exc),
                            exc_info=True)
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
        salt.utils.daemonize_if(self.opts)

        salt.transport.jobber_stack = stack = self._setup_jobber_stack()
        # set up return destination from source
        src_estate, src_yard, src_share = msg['route']['src']
        salt.transport.jobber_estate_name = src_estate
        salt.transport.jobber_yard_name = src_yard

        sdata = {'pid': os.getpid()}
        sdata.update(data)
        with salt.utils.fopen(fn_, 'w+b') as fp_:
            fp_.write(self.serial.dumps(sdata))
        ret = {'success': False}
        function_name = data['fun']
        if function_name in self.modules.value:
            try:
                func = self.modules.value[data['fun']]
                args, kwargs = salt.minion.load_args_and_kwargs(
                    func,
                    salt.utils.args.parse_input(data['arg']),
                    data)
                sys.modules[func.__module__].__context__['retcode'] = 0

                executors = data.get('module_executors') or self.opts.get('module_executors', ['direct_call.get'])
                if isinstance(executors, six.string_types):
                    executors = [executors]
                elif not isinstance(executors, list) or not executors:
                    raise SaltInvocationError("Wrong executors specification: {0}. String or non-empty list expected".
                                              format(executors))
                if self.opts.get('sudo_user', '') and executors[-1] != 'sudo.get':
                    if executors[-1] in FUNCTION_EXECUTORS:
                        executors[-1] = 'sudo.get'  # replace
                    else:
                        executors.append('sudo.get')  # append
                log.trace("Executors list {0}".format(executors))

                # Get executors
                def get_executor(name):
                    executor_class = self.module_executors.value.get(name)
                    if executor_class is None:
                        raise SaltInvocationError("Executor '{0}' is not available".format(name))
                    return executor_class
                # Get the last one that is function executor
                executor = get_executor(executors.pop())(self.opts, data, func, args, kwargs)
                # Instantiate others from bottom to the top
                for executor_name in reversed(executors):
                    executor = get_executor(executor_name)(self.opts, data, executor)
                return_data = executor.execute()

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
                                [data['jid'], 'prog', self.opts['id'], str(ind)],
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
                    'A command in \'{0}\' had a problem: {1}'.format(
                        function_name,
                        exc
                    ),
                    exc_info_on_loglevel=logging.DEBUG
                )
                ret['return'] = 'ERROR: {0}'.format(exc)
            except SaltInvocationError as exc:
                log.error(
                    'Problem executing \'{0}\': {1}'.format(
                        function_name,
                        exc
                    ),
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
                    log.error(
                        'The return failed for job {0} {1}'.format(
                        data['jid'],
                        exc
                        )
                    )
        console.concise("Closing Jobber Stack {0}\n".format(stack.name))
        stack.server.close()
        salt.transport.jobber_stack = None
