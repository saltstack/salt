# -*- coding: utf-8 -*-
'''
The behaviors to run the salt minion via ioflo
'''

# Import python libs
import os
import logging
import sys
import types
import traceback
import multiprocessing
from collections import deque

# Import salt libs
import salt.minion
import salt.payload
import salt.utils
import salt.utils.event
import salt.daemons.masterapi
import salt.utils.schedule
from salt.exceptions import (
        CommandExecutionError, CommandNotFoundError, SaltInvocationError)
from salt.transport.road.raet import yarding
from salt.transport.road.raet import stacking

# Import ioflo libs
import ioflo.base.deeding

# Import Third Party Libs
HAS_PSUTIL = False
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    pass

HAS_RESOURCE = False
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    pass
log = logging.getLogger(__name__)


class RouterMinion(ioflo.base.deeding.Deed):  # pylint: disable=W0232
    '''
    Route packaets from raet into minion proessing bins
    '''
    Ioinits = {'opts': '.salt.opts',
               'udp_stack': '.raet.udp.stack.stack',
               'uxd_stack': '.salt.uxd.stack.stack',
               'fun_in': '.salt.net.fun_in',
               }

    def postinitio(self):
        '''
        Map opts for convenience
        '''
        self.uxd_stack.value = stacking.StackUxd(
                lanename=self.opts.value['id'],
                yid=0,
                dirpath=self.opts.value['sock_dir'])
        self.fun_in.value = deque()

    def action(self):
        '''
        Empty the queues into process management queues
        '''
        # Start on the udp_in:
        # TODO: Route UXD messages
        while self.udp_stack.value.rxMsgs:
            data = self.udp_stack.value.rxMsgs.popleft()
            if data['route']['dst'][2] == 'fun':
                self.fun_in.value.append(data)
            if data['route']['dst'][1] is not None:
                if data['route']['dst'][1] in self.uxd_stack.value.yards:
                    self.uxd_stack.value.transmit(data, data['route']['dst'][1])
        self.uxd_stack.value.serviceAll()
        while self.uxd_stack.value.rxMsgs:
            msg = self.uxd_stack.value.rxMsgs.popleft()
            estate = msg['route']['dst'][0]
            if estate is not None:
                if estate != self.opts.value['id']:
                    self.udp_stack.value.message(
                            msg,
                            self.udp_stack.value.eids[estate])



class PillarLoad(ioflo.base.deeding.Deed):  # pylint: disable=W0232
    '''
    Load up the pillar in the data store
    '''
    Ioinits = {'opts_store': '.salt.opts',
               'grains': '.salt.loader.grains'}


class ModulesLoad(ioflo.base.deeding.Deed):  # pylint: disable=W0232
    '''
    Reload the minion modules
    '''
    Ioinits = {'opts_store': '.salt.opts',
               'grains': '.salt.loader.grains',
               'modules': '.salt.loader.modules',
               'returners': '.salt.loader.returners'}

    def postinitio(self):
        '''
        Map opts for convenience
        '''
        self.opts = self.opts_store.value

    def action(self):
        '''
        Return the functions and the returners loaded up from the loader
        module
        '''
        # if this is a *nix system AND modules_max_memory is set, lets enforce
        # a memory limit on module imports
        # this feature ONLY works on *nix like OSs (resource module doesn't work on windows)
        modules_max_memory = False
        if self.opts.get('modules_max_memory', -1) > 0 and HAS_PSUTIL and HAS_RESOURCE:
            log.debug(
                    'modules_max_memory set, enforcing a maximum of {0}'.format(
                        self.opts['modules_max_memory'])
                    )
            modules_max_memory = True
            old_mem_limit = resource.getrlimit(resource.RLIMIT_AS)
            rss, vms = psutil.Process(os.getpid()).get_memory_info()
            mem_limit = rss + vms + self.opts['modules_max_memory']
            resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
        elif self.opts.get('modules_max_memory', -1) > 0:
            if not HAS_PSUTIL:
                log.error('Unable to enforce modules_max_memory because psutil is missing')
            if not HAS_RESOURCE:
                log.error('Unable to enforce modules_max_memory because resource is missing')

        self.opts['grains'] = salt.loader.grains(self.opts)
        self.grains.value = self.opts['grains']
        self.modules.value = salt.loader.minion_mods(self.opts)
        self.returners.value = salt.loader.returners(self.opts, self.modules.value)

        # we're done, reset the limits!
        if modules_max_memory is True:
            resource.setrlimit(resource.RLIMIT_AS, old_mem_limit)


class Schedule(ioflo.base.deeding.Deed):  # pylint: disable=W0232
    '''
    Evaluates the scedule
    '''
    Ioinits = {'opts_store': '.salt.opts',
               'grains': '.salt.grains',
               'modules': '.salt.loader.modules',
               'returners': '.salt.loader.returners',
               'master_ret': '.salt.net.master_out'}

    def postinitio(self):
        '''
        Map opts and make the scedule object
        '''
        self.scedule = salt.utils.schedule.Schedule(
                self.opts.value,
                self.modules.value,
                self.returners.value)

    def action(self):
        '''
        Eval the schedule
        '''
        self.scedule.eval()


class FunctionNix(ioflo.base.deeding.Deed):  # pylint: disable=W0232
    '''
    Execute a function call
    '''
    Ioinits = {'opts_store': '.salt.opts',
               'grains': '.salt.grains',
               'modules': '.salt.loader.modules',
               'returners': '.salt.loader.returners',
               'fun_ack': '.salt.net.fun_ack',
               'fun_in': '.salt.net.fun_in',
               'master_ret': '.salt.net.master_out',
               'uxd_stack': '.salt.uxd.stack.stack',
               'executors': '.salt.track.executors'}

    def postinitio(self):
        '''
        Map opts for convenience
        '''
        self.opts = self.opts_store.value
        self.matcher = salt.minion.Matcher(
                self.opts,
                self.modules.value)
        self.proc_dir = salt.minion.get_proc_dir(self.opts['cachedir'])
        self.serial = salt.payload.Serial(self.opts)
        self.executors.value = {}

    def _return_pub(self, ret):
        '''
        Send the return data back via the uxd socket
        '''
        ret_stack = stacking.StackUxd(
                lanename=self.opts['id'],
                yid=ret['jid'],
                dirpath=self.opts['sock_dir'])
        main_yard = yarding.Yard(
                yid=0,
                prefix=self.opts['id'],
                dirpath=self.opts['sock_dir']
                )
        ret_stack.addRemoteYard(main_yard)
        route = {'src': (self.opts['id'], ret_stack.yard.name, 'jid_ret'),
                 'dst': ('master', None, 'return')}
        msg = {'route': route, 'return': ret}
        ret_stack.transmit(msg, 'yard0')
        ret_stack.serviceAll()

    def action(self):
        '''
        Pull the queue for functions to execute
        '''
        if not self.fun_in.value:
            return
        exchange = self.fun_in.value.popleft()
        data = exchange.get('pub')
        # convert top raw strings - take this out once raet is using msgpack
        for key, val in data.items():
            if isinstance(val, basestring):
                data[str(key)] = str(val)
            else:
                data[str(key)] = val
        match = getattr(
                self.matcher,
                '{0}_match'.format(
                    data.get('tgt_type', 'glob')
                    )
                )(data['tgt'])
        if not match:
            return
        if 'user' in data:
            log.info(
                    'User {0[user]} Executing command {0[fun]} with jid '
                    '{0[jid]}'.format(data))
        else:
            log.info(
                    'Executing command {0[fun]} with jid {0[jid]}'.format(data)
                    )
        log.debug('Command details {0}'.format(data))
        ex_yard = yarding.Yard(
                yid=data['jid'],
                prefix=self.opts['id'],
                dirpath=self.opts['sock_dir'])
        self.uxd_stack.value.addRemoteYard(ex_yard)
        process = multiprocessing.Process(
                target=self.proc_run,
                kwargs={'exchange': exchange}
                )
        process.start()  # Don't join this process! The process daemonizes
                         # itself and init will clean it up

    def proc_run(self, exchange):
        '''
        Execute the run in a dedicated process
        '''
        data = exchange['pub']
        fn_ = os.path.join(self.proc_dir, data['jid'])
        self.opts['__ex_id'] = data['jid']
        salt.utils.daemonize_if(self.opts)
        sdata = {'pid': os.getpid()}
        sdata.update(data)
        with salt.utils.fopen(fn_, 'w+') as fp_:
            fp_.write(self.serial.dumps(sdata))
        ret = {'success': False}
        function_name = data['fun']
        if function_name in self.modules.value:
            try:
                func = self.modules.value[data['fun']]
                args, kwargs = salt.minion.parse_args_and_kwargs(func, data['arg'], data)
                sys.modules[func.__module__].__context__['retcode'] = 0
                return_data = func(*args, **kwargs)
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
                        tag = salt.utils.event.tagify(
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
                msg = 'Command required for {0!r} not found'.format(
                    function_name
                )
                log.debug(msg, exc_info=True)
                ret['return'] = '{0}: {1}'.format(msg, exc)
            except CommandExecutionError as exc:
                log.error(
                    'A command in {0!r} had a problem: {1}'.format(
                        function_name,
                        exc
                    ),
                    exc_info=log.isEnabledFor(logging.DEBUG)
                )
                ret['return'] = 'ERROR: {0}'.format(exc)
            except SaltInvocationError as exc:
                log.error(
                    'Problem executing {0!r}: {1}'.format(
                        function_name,
                        exc
                    ),
                    exc_info=log.isEnabledFor(logging.DEBUG)
                )
                ret['return'] = 'ERROR executing {0!r}: {1}'.format(
                    function_name, exc
                )
            except TypeError as exc:
                aspec = salt.utils.get_function_argspec(
                    self.modules.value[data['fun']]
                )
                msg = ('TypeError encountered executing {0}: {1}. See '
                       'debug log for more info.  Possibly a missing '
                       'arguments issue:  {2}').format(function_name,
                                                       exc,
                                                       aspec)
                log.warning(msg, exc_info=log.isEnabledFor(logging.DEBUG))
                ret['return'] = msg
            except Exception:
                msg = 'The minion function caused an exception'
                log.warning(msg, exc_info=log.isEnabledFor(logging.DEBUG))
                ret['return'] = '{0}: {1}'.format(msg, traceback.format_exc())
        else:
            ret['return'] = '{0!r} is not available.'.format(function_name)

        ret['jid'] = data['jid']
        ret['fun'] = data['fun']
        ret['fun_args'] = data['arg']
        self._return_pub(ret)
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
