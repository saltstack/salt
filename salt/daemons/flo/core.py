# -*- coding: utf-8 -*-
'''
The core bahaviuors ued by minion and master
'''
# pylint: disable=W0232

# Import python libs
import os
import sys
import types
import logging
import multiprocessing
import traceback
import itertools
from collections import deque

# Import salt libs
import salt.daemons.masterapi
from salt.transport.road.raet import stacking
from salt.transport.road.raet import yarding
from salt.exceptions import (
        CommandExecutionError, CommandNotFoundError, SaltInvocationError)

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


class ModulesLoad(ioflo.base.deeding.Deed):
    '''
    Reload the minion modules
    '''
    Ioinits = {'opts': '.salt.opts',
               'grains': '.salt.grains',
               'modules': '.salt.loader.modules',
               'returners': '.salt.loader.returners'}

    def action(self):
        '''
        Return the functions and the returners loaded up from the loader
        module
        '''
        # if this is a *nix system AND modules_max_memory is set, lets enforce
        # a memory limit on module imports
        # this feature ONLY works on *nix like OSs (resource module doesn't work on windows)
        modules_max_memory = False
        if self.opts.value.get('modules_max_memory', -1) > 0 and HAS_PSUTIL and HAS_RESOURCE:
            log.debug(
                    'modules_max_memory set, enforcing a maximum of {0}'.format(
                        self.opts.value['modules_max_memory'])
                    )
            modules_max_memory = True
            old_mem_limit = resource.getrlimit(resource.RLIMIT_AS)
            rss, vms = psutil.Process(os.getpid()).get_memory_info()
            mem_limit = rss + vms + self.opts.value['modules_max_memory']
            resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
        elif self.opts.value.get('modules_max_memory', -1) > 0:
            if not HAS_PSUTIL:
                log.error('Unable to enforce modules_max_memory because psutil is missing')
            if not HAS_RESOURCE:
                log.error('Unable to enforce modules_max_memory because resource is missing')

        self.opts.value['grains'] = salt.loader.grains(self.opts.value)
        self.grains.value = self.opts.value['grains']
        self.modules.value = salt.loader.minion_mods(self.opts.value)
        self.returners.value = salt.loader.returners(self.opts.value, self.modules.value)

        # we're done, reset the limits!
        if modules_max_memory is True:
            resource.setrlimit(resource.RLIMIT_AS, old_mem_limit)


class Schedule(ioflo.base.deeding.Deed):
    '''
    Evaluates the schedule
    '''
    Ioinits = {'opts_store': '.salt.opts',
               'grains': '.salt.grains',
               'modules': '.salt.loader.modules',
               'returners': '.salt.loader.returners'}

    def postinitio(self):
        '''
        Map opts and make the schedule object
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


class Setup(ioflo.base.deeding.Deed):
    '''
    Only intended to be called once at the top of the house
    '''
    Ioinits = {'opts': '.salt.opts',
               'event_yards': '.salt.event.yards',
               'local_cmd': '.salt.local.local_cmd',
               'remote_cmd': '.salt.local.remote_cmd',
               'publish': '.salt.local.publish',
               'fun': '.salt.local.fun',
               'event': '.salt.event.events',
               'event_req': '.salt.event.event_req',
               'workers': '.salt.track.workers',
               'uxd_stack': '.salt.uxd.stack.stack'}

    def postinitio(self):
        '''
        Set up required objects and queues
        '''
        self.uxd_stack.value = stacking.StackUxd(
                lanename=self.opts.value['id'],
                yid=0,
                dirpath=self.opts.value['sock_dir'])
        self.event_yards.value = set()
        self.local_cmd.value = deque()
        self.remote_cmd.value = deque()
        self.fun.value = deque()
        self.event.value = deque()
        self.event_req.value = deque()
        self.publish.value = deque()
        worker_seed = []
        for ind in range(self.opts.value['worker_threads']):
            worker_seed.append('yard{0}'.format(ind + 1))
        self.workers.value = itertools.cycle(worker_seed)


class Rx(ioflo.base.deeding.Deed):
    '''
    Process the inbound udp traffic
    '''
    Ioinits = {
               'uxd_stack': '.salt.uxd.stack.stack',
               'udp_stack': '.raet.udp.stack.stack',
               }

    def action(self):
        '''
        Process inboud queues
        '''
        self.udp_stack.value.serviceAll()
        self.uxd_stack.value.serviceAll()


class Tx(ioflo.base.deeding.Deed):
    '''
    Process the inbound udp traffic
    '''
    # Yes, this class is identical to RX, this is because we still need to
    # separate out rx and tx in raet itself
    Ioinits = {
               'uxd_stack': '.salt.uxd.stack.stack',
               'udp_stack': '.raet.udp.stack.stack',
               }

    def action(self):
        '''
        Process inbound queues
        '''
        self.uxd_stack.value.serviceAll()
        self.udp_stack.value.serviceAll()


class Router(ioflo.base.deeding.Deed):
    '''
    Routes the communication in and out of uxd connections
    '''
    Ioinits = {'opts': '.salt.opts',
               'local_cmd': '.salt.local.local_cmd',
               'remote_cmd': '.salt.local.remote_cmd',
               'publish': '.salt.local.publish',
               'fun': '.salt.local.fun',
               'event': '.salt.event.events',
               'event_req': '.salt.event.event_req',
               'uxd_stack': '.salt.uxd.stack.stack',
               'udp_stack': '.raet.udp.stack.stack'}

    def postinitio(self):
        self.next_worker  # pylint: disable=W0104

    def _process_udp_rxmsg(self, msg):
        '''
        Send to the right queue
        '''
        try:
            d_estate = msg['route']['dst'][0]
            d_yard = msg['route']['dst'][1]
            d_share = msg['route']['dst'][2]
        except (ValueError, IndexError):
            log.error('Received invalid message: {0}'.format(msg))
            return
        if d_estate != self.udp_stack.value.estate:
            log.error(
                    'Received message for wrong estate: {0}'.format(d_estate))
            return
        if d_yard is not None:
            # Meant for another yard, send it off!
            if d_yard in self.uxd_stack.value.yards:
                self.uxd_stack.value.transmit(msg, d_yard)
                return
            return
        if d_share is None:
            # No queue destination!
            log.error('Received message without share: {0}'.format(msg))
            return
        if d_share == 'local_cmd':
            # Refuse local commands over the wire
            log.error('Received local command remotely! Ignoring: {0}'.format(msg))
            return
        if d_share == 'remote_cmd':
            # Send it to a remote worker
            self.uxd_stack.value.transmit(msg, next(self.workers.value))

    def _process_uxd_rxmsg(self, msg):
        '''
        Send uxd messages tot he right queue or forward them to the correct
        yard etc.
        '''
        try:
            d_estate = msg['route']['dst'][0]
            d_yard = msg['route']['dst'][1]
            d_share = msg['route']['dst'][2]
        except (ValueError, IndexError):
            log.error('Received invalid message: {0}'.format(msg))
            return
        if d_estate is None:
            pass
        elif d_estate != self.udp_stack.value.estate:
            # Forward to the correct estate
            eid = self.udp_stack.value.eids.get(d_estate)
            self.udp_stack.value.message(msg, eid)
            return
        if d_yard is not None:
            # Meant for another yard, send it off!
            if d_yard in self.uxd_stack.value.yards:
                self.uxd_stack.value.transmit(msg, d_yard)
                return
            return
        if d_share is None:
            # No queue destination!
            log.error('Received message without share: {0}'.format(msg))
            return
        if d_share == 'local_cmd':
            self.uxd_stack.value.transmit(msg, next(self.workers.value))

    def action(self):
        '''
        Process the messages!
        '''
        while self.udp_stack.value.rxMsgs:
            self._process_udp_rxmsg(self.udp_stack.value.rxMsgs.popleft())
        while self.uxd_stack.value.rxMsgs:
            self._process_uxd_rxmsg(self.uxd_stack.value.rxMsgs.popleft())


class Eventer(ioflo.base.deeding.Deed):
    '''
    Fire events!
    '''
    Ioinits = {'opts': '.salt.opts',
               'event_yards': '.salt.event.yards',
               'event': '.salt.event.events',
               'event_req': '.salt.event.event_req',
               'uxd_stack': '.salt.uxd.stack.stack'}

    def _register_event_yard(self, msg):
        '''
        register an incoming event request with the requesting yard id
        '''
        ev_yard = yarding.Yard(
                yid=msg['load']['yid'],
                prefix='master',
                dirpath=msg['load']['dirpath'])
        self.event_yards.value.add(ev_yard.name)

    def _fire_event(self, event):
        '''
        Fire an event to all subscribed yards
        '''
        for y_name in self.event_yards.value:
            route = {'src': ('router', self.stack.value.yard.name, None),
                     'dst': ('router', y_name, None)}
            msg = {'route': route, 'event': event}
            self.uxd_stack.value.transmit(msg, y_name)

    def action(self):
        '''
        Register event requests
        Iterate over the registered event yards and fire!
        '''
        while self.event_req.value:
            self._register_event_yard(
                    self.event_req.value.popleft()
                    )

        while self.event.value:
            self._fire_event(
                    self.event.value.popleft()
                    )


class Publisher(ioflo.base.deeding.Deed):
    '''
    Publish to the minions
    '''
    Ioinits = {'opts': '.salt.opts',
               'publish': '.salt.local.publish',
               'udp_stack': '.raet.udp.stack.stack'}

    def _publish(self, pub_msg):
        '''
        Publish the message out to the targeted minions
        '''
        for minion in self.udp_stack.value.eids:
            eid = self.udp_stack.value.eids.get(minion)
            if eid:
                route = {'dst': (minion, None, 'fun')}
                msg = {'route': route, 'pub': pub_msg['pub']}
                self.udp_stack.value.message(msg, eid)

    def action(self):
        '''
        Pop the publish queue and publish the requests!
        '''
        while self.publish.value:
            self._publish(
                    self.publish.value.popleft()
                    )


class ExecutorNix(ioflo.base.deeding.Deed):
    '''
    Execute a function call on a *nix based system
    '''
    Ioinits = {'opts_store': '.salt.opts',
               'grains': '.salt.grains',
               'modules': '.salt.loader.modules',
               'returners': '.salt.loader.returners',
               'fun': '.salt.local.fun',
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
        while self.fun.value:
            exchange = self.fun.value.popleft()
            data = exchange.get('pub')
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
            process.start()
            process.join()

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
