# -*- coding: utf-8 -*-
'''
The core behaviors used by minion and master
'''
# pylint: disable=W0232

# Import python libs
import os
import sys
import time
import types
import logging
import multiprocessing
import traceback
import itertools
from collections import deque

# Import salt libs
import salt.daemons.masterapi
import salt.utils.args
import salt.transport
from raet import raeting, nacling
from raet.road.stacking import RoadStack
from raet.road.estating import LocalEstate
from raet.lane.stacking import LaneStack
from raet.lane.yarding import RemoteYard

from salt.daemons import salting

from salt.exceptions import (
        CommandExecutionError, CommandNotFoundError, SaltInvocationError)

# Import ioflo libs
from ioflo.base.odicting import odict
import ioflo.base.deeding

from ioflo.base.consoling import getConsole
console = getConsole()

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


class SaltRaetCleanup(ioflo.base.deeding.Deed):
    '''
    Cleanup stray lane keep directories not reaped

    FloScript:

    do salt raet cleanup at enter

    '''
    Ioinits = {
                'opts': '.salt.opts',
            }

    def action(self):
        '''
        Should only run once to cleanup stale lane uxd files.
        '''
        if self.opts.value.get('sock_dir'):
            sockdirpath = os.path.abspath(self.opts.value['sock_dir'])
            console.concise("Cleaning up uxd files in {0}\n".format(sockdirpath))
            for name in os.listdir(sockdirpath):
                path = os.path.join(sockdirpath, name)
                if os.path.isdir(path):
                    continue
                root, ext = os.path.splitext(name)
                if ext != '.uxd':
                    continue
                if not all(root.partition('.')):
                    continue
                try:
                    os.unlink(path)
                    console.concise("Removed {0}\n".format(path))
                except OSError:
                    console.concise("Failed removing {0}\n".format(path))
                    raise


class SaltRaetRoadStackSetup(ioflo.base.deeding.Deed):
    '''
    Initialize and run raet udp stack for Salt
    FloScript:

    do salt raet road stack setup at enter

    '''
    Ioinits = {
            'inode': 'raet.udp.stack.',
            'stack': 'stack',
            'opts': '.salt.opts',
            'txmsgs': {'ipath': 'txmsgs',
                       'ival': deque()},
            'rxmsgs': {'ipath': 'rxmsgs',
                       'ival': deque()},
            'local': {'ipath': 'local',
                      'ival': {'name': 'master',
                               'main': False,
                               'auto': None,
                               'eid': 0,
                               'sigkey': None,
                               'prikey': None}},
            }

    def postinitio(self):
        '''
        Assign class defaults
        '''
        RoadStack.Bk = raeting.bodyKinds.msgpack
        RoadStack.JoinentTimeout = 0.0

    def action(self):
        '''
        enter action
        should only run once to setup road stack.
        moved from postinitio so can do clean up before stack is initialized

        do salt raet road stack setup at enter
        '''
        name = self.opts.value.get('id', self.local.data.name)
        sigkey = self.local.data.sigkey
        prikey = self.local.data.prikey
        auto = self.local.data.auto
        main = self.local.data.main
        eid = self.local.data.eid

        ha = (self.opts.value['interface'], self.opts.value['raet_port'])

        basedirpath = os.path.abspath(os.path.join(self.opts.value['cachedir'], 'raet'))

        local = LocalEstate(
                eid=eid,
                name=name,
                main=main,
                ha=ha,
                sigkey=sigkey,
                prikey=prikey)
        txMsgs = self.txmsgs.value
        rxMsgs = self.rxmsgs.value

        keep = salting.SaltKeep(opts=self.opts.value,
                                basedirpath=basedirpath,
                                stackname=name,
                                auto=auto)

        self.stack.value = RoadStack(
                local=local,
                store=self.store,
                name=name,
                main=main,
                keep=keep,
                txMsgs=txMsgs,
                rxMsgs=rxMsgs,
                period=3.0,
                offset=0.5)


class SaltRaetRoadStackCloser(ioflo.base.deeding.Deed):
    '''
    Closes stack server socket connection
    FloScript:

    do salt raet road stack closer at exit

    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack', )

    def action(self, **kwa):
        '''
        Close udp socket
        '''
        if self.stack.value and isinstance(self.stack.value, RoadStack):
            self.stack.value.server.close()


class SaltRaetRoadStackJoiner(ioflo.base.deeding.Deed):
    '''
    Initiates join transaction with master
    FloScript:

    do salt raet road stack joiner at enter

    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack',
        masterhost='.salt.etc.master',
        masterport='.salt.etc.master_port', )

    def postinitio(self):
        self.mha = (self.masterhost.value, int(self.masterport.value))

    def action(self, **kwa):
        '''
        Receive any udp packets on server socket and put in rxes
        Send any packets in txes
        '''
        stack = self.stack.value
        if stack and isinstance(stack, RoadStack):
            stack.join(ha=self.mha, timeout=0.0)


class SaltRaetRoadStackJoined(ioflo.base.deeding.Deed):
    '''
    Updates status with .joined of zeroth remote estate (master)
    FloScript:

    do salt raet road stack joined
    go next if joined in .raet.udp.stack.status

    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack',
        status=odict(ipath='status', ival=odict(joined=False,
                                                allowed=False,
                                                alived=False,
                                                rejected=False,
                                                idle=False, )))

    def action(self, **kwa):
        '''
        Update .status share
        '''
        stack = self.stack.value
        joined = False
        if stack and isinstance(stack, RoadStack):
            if stack.remotes:
                joined = stack.remotes.values()[0].joined
        self.status.update(joined=joined)


class SaltRaetRoadStackRejected(ioflo.base.deeding.Deed):
    '''
    Updates status with rejected of .acceptance of zeroth remote estate (master)
    FloScript:

    do salt raet road stack rejected
    go next if rejected in .raet.udp.stack.status

    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack',
        status=odict(ipath='status', ival=odict(joined=False,
                                                allowed=False,
                                                alived=False,
                                                rejected=False,
                                                idle=False, )))

    def action(self, **kwa):
        '''
        Update .status share
        '''
        stack = self.stack.value
        rejected = False
        if stack and isinstance(stack, RoadStack):
            if stack.remotes:
                rejected = (stack.remotes.values()[0].acceptance
                                == raeting.acceptances.rejected)
            else:  # no remotes so assume rejected
                rejected = True
        self.status.update(rejected=rejected)


class SaltRaetRoadStackAllower(ioflo.base.deeding.Deed):
    '''
    Initiates allow (CurveCP handshake) transaction with master
    FloScript:

    do salt raet road stack allower at enter

    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack', )

    def action(self, **kwa):
        '''
        Receive any udp packets on server socket and put in rxes
        Send any packets in txes
        '''
        stack = self.stack.value
        if stack and isinstance(stack, RoadStack):
            stack.allow(timeout=0.0)
        return None


class SaltRaetRoadStackAllowed(ioflo.base.deeding.Deed):
    '''
    Updates status with .allowed of zeroth remote estate (master)
    FloScript:

    do salt raet road stack allowed
    go next if allowed in .raet.udp.stack.status

    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack',
        status=odict(ipath='status', ival=odict(joined=False,
                                                allowed=False,
                                                alived=False,
                                                rejected=False,
                                                idle=False, )))

    def action(self, **kwa):
        '''
        Update .status share
        '''
        stack = self.stack.value
        allowed = False
        if stack and isinstance(stack, RoadStack):
            if stack.remotes:
                allowed = stack.remotes.values()[0].allowed
        self.status.update(allowed=allowed)


class SaltRaetRoadStackManager(ioflo.base.deeding.Deed):
    '''
    Runs the manage method of RoadStack
    FloScript:
        do salt raet road stack manager

    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack',
        alloweds={'ipath': '.salt.var.presence.alloweds',
                  'ival': odict()},
        aliveds={'ipath': '.salt.var.presence.aliveds',
                 'ival': odict()},
        reapeds={'ipath': '.salt.var.presence.reapeds',
                         'ival': odict()},
        availables={'ipath': '.salt.var.presence.availables',
                    'ival': set()},
        changeds={'ipath': '.salt.var.presence.changeds',
                  'ival': odict(plus=set(), minus=set())},)

    def action(self, **kwa):
        '''
        Manage the presence of any remotes

        availables is set of names of alive remotes which are also allowed
        changeds is is share with two fields:
            plus is set of names of newly available remotes
            minus is set of names of newly unavailable remotes
        alloweds is dict of allowed remotes keyed by name
        aliveds is dict of alived remotes keyed by name
        reapeds is dict of reaped remotes keyed by name
        '''
        stack = self.stack.value
        if stack and isinstance(stack, RoadStack):
            stack.manage(cascade=True)
            # make copies
            self.availables.value = set(self.stack.value.availables)
            self.changeds.update(plus=set(self.stack.value.changeds['plus']))
            self.changeds.update(minus=set(self.stack.value.changeds['minus']))
            self.alloweds.value = odict(self.stack.value.alloweds)
            self.aliveds.value = odict(self.stack.value.aliveds)
            self.reapeds.value = odict(self.stack.value.reapeds)

            console.concise(" Manage {0}.\nAvailables: {1}\nChangeds:\nPlus: {2}\n"
                            "Minus: {3}\nAlloweds: {4}\nAliveds: {5}\nReapeds: {6}\n".format(
                    stack.name,
                    self.availables.value,
                    self.changeds.data.plus,
                    self.changeds.data.minus,
                    self.alloweds.value,
                    self.aliveds.value,
                    self.reapeds.value))
            # need to queue presence event message if either plus or minus is not empty


class SaltRaetRoadStackPrinter(ioflo.base.deeding.Deed):
    '''
    Prints out messages on rxMsgs queue for associated stack
    FloScript:

    do raet road stack printer

    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        rxmsgs=odict(ipath='rxmsgs', ival=deque()),)

    def action(self, **kwa):
        '''
        Queue up message
        '''
        rxMsgs = self.rxmsgs.value
        while rxMsgs:
            msg, name = rxMsgs.popleft()
            console.terse("\nReceived....\n{0}\n".format(msg))


class LoadModules(ioflo.base.deeding.Deed):
    '''
    Reload the minion modules
    FloScript:

    do load modules at enter

    '''
    Ioinits = {'opts': '.salt.opts',
               'grains': '.salt.grains',
               'modules': '.salt.loader.modules',
               'grain_time': '.salt.var.grain_time',
               'module_refresh': '.salt.var.module_refresh',
               'returners': '.salt.loader.returners'}

    def postinitio(self):
        self._load_modules()

    def action(self):
        self._load_modules()

    def _load_modules(self):
        '''
        Return the functions and the returners loaded up from the loader
        module
        '''
        if self.grain_time.value is None:
            self.grain_time.value = 0.0
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

        if time.time() - self.grain_time.value > 300.0 or self.module_refresh.value:
            self.opts.value['grains'] = salt.loader.grains(self.opts.value)
            self.grain_time.value = time.time()
            self.grains.value = self.opts.value['grains']
        self.modules.value = salt.loader.minion_mods(self.opts.value)
        self.returners.value = salt.loader.returners(self.opts.value, self.modules.value)

        # we're done, reset the limits!
        if modules_max_memory is True:
            resource.setrlimit(resource.RLIMIT_AS, old_mem_limit)
        self.module_refresh.value = False


class LoadPillar(ioflo.base.deeding.Deed):
    '''
    Load up the initial pillar for the minion
    '''
    Ioinits = {'opts': '.salt.opts',
               'pillar': '.salt.pillar',
               'grains': '.salt.grains',
               'modules': '.salt.loader.modules',
               'pillar_refresh': '.salt.var.pillar_refresh',
               'udp_stack': '.raet.udp.stack.stack'}

    def action(self):
        '''
        Initial pillar
        '''
        route = {'src': (self.opts.value['id'], 0, None),
                 'dst': ('master', None, 'remote_cmd')}
        load = {'id': self.opts.value['id'],
                'grains': self.grains.value,
                'saltenv': self.opts.value['environment'],
                'ver': '2',
                'cmd': '_pillar'}
        self.udp_stack.value.transmit({'route': route, 'load': load})
        self.udp_stack.value.serviceAll()
        while True:
            time.sleep(0.1)
            while self.udp_stack.value.rxMsgs:
                msg, sender = self.udp_stack.value.rxMsgs.popleft()
                self.pillar.value = msg.get('return', {})
                if self.pillar.value is None:
                    continue
                self.opts.value['pillar'] = self.pillar.value
                self.pillar_refresh.value = False
                return
            self.udp_stack.value.serviceAll()
        self.pillar_refresh.value = False


class Schedule(ioflo.base.deeding.Deed):
    '''
    Evaluates the schedule
    FloScript:

    do schedule

    '''
    Ioinits = {'opts': '.salt.opts',
               'grains': '.salt.grains',
               'modules': '.salt.loader.modules',
               'returners': '.salt.loader.returners'}

    def postinitio(self):
        '''
        Map opts and make the schedule object
        '''
        self.modules.value = salt.loader.minion_mods(self.opts.value)
        self.returners.value = salt.loader.returners(self.opts.value, self.modules.value)
        self.schedule = salt.utils.schedule.Schedule(
                self.opts.value,
                self.modules.value,
                self.returners.value)

    def action(self):
        '''
        Eval the schedule
        '''
        self.schedule.eval()


class SaltManorLaneSetup(ioflo.base.deeding.Deed):
    '''
    Only intended to be called once at the top of the manor house
    Sets up the LaneStack for the main yard
    FloScript:

    do salt manor lane setup at enter

    '''
    Ioinits = {'opts': '.salt.opts',
               'event_yards': '.salt.event.yards',
               'local_cmd': '.salt.var.local_cmd',
               'remote_cmd': '.salt.var.remote_cmd',
               'publish': '.salt.var.publish',
               'fun': '.salt.var.fun',
               'worker_verify': '.salt.var.worker_verify',
               'event': '.salt.event.events',
               'event_req': '.salt.event.event_req',
               'workers': '.salt.track.workers',
               'inode': '.salt.uxd.stack.',
               'stack': 'stack',
               'local': {'ipath': 'local',
                          'ival': {'name': 'master',
                                   'yid': 0,
                                   'lanename': 'master'}},
            }

    def postinitio(self):
        '''
        Set up required objects and queues
        '''
        pass

    def action(self):
        '''
        Run once at enter
        '''
        #name = "{0}{1}".format(self.opts.value.get('id', self.local.data.name), 'lane')
        name = 'manor'
        lanename = self.opts.value.get('id', self.local.data.lanename)
        yid = self.local.data.yid
        self.stack.value = LaneStack(
                                    name=name,
                                    lanename=lanename,
                                    yid=0,
                                    sockdirpath=self.opts.value['sock_dir'])
        self.stack.value.Pk = raeting.packKinds.pack
        self.event_yards.value = set()
        self.local_cmd.value = deque()
        self.remote_cmd.value = deque()
        self.fun.value = deque()
        self.event.value = deque()
        self.event_req.value = deque()
        self.publish.value = deque()
        self.worker_verify.value = salt.utils.rand_string()
        if self.opts.value.get('worker_threads'):
            worker_seed = []
            for ind in range(self.opts.value['worker_threads']):
                worker_seed.append('worker{0}'.format(ind + 1))
            self.workers.value = itertools.cycle(worker_seed)


class SaltRaetLaneStackCloser(ioflo.base.deeding.Deed):  # pylint: disable=W0232
    '''
    Closes lane stack server socket connection
    FloScript:

    do raet lane stack closer at exit

    '''
    Ioinits = odict(
        inode=".salt.uxd.stack",
        stack='stack',)

    def action(self, **kwa):
        '''
        Close uxd socket
        '''
        if self.stack.value and isinstance(self.stack.value, LaneStack):
            self.stack.value.server.close()


class SaltRaetRoadStackService(ioflo.base.deeding.Deed):
    '''
    Process the udp traffic
    FloScript:

    do rx

    '''
    Ioinits = {
               'udp_stack': '.raet.udp.stack.stack',
               }

    def action(self):
        '''
        Process inboud queues
        '''
        self.udp_stack.value.serviceAll()


class SaltRaetRoadStackServiceRx(ioflo.base.deeding.Deed):
    '''
    Process the inbound udp traffic
    FloScript:

    do rx

    '''
    Ioinits = {
               'uxd_stack': '.salt.uxd.stack.stack',
               'udp_stack': '.raet.udp.stack.stack',
               }

    def action(self):
        '''
        Process inboud queues
        '''
        self.udp_stack.value.serviceAllRx()
        self.uxd_stack.value.serviceAllRx()


class SaltRaetRoadStackServiceTx(ioflo.base.deeding.Deed):
    '''
    Process the inbound udp traffic
    FloScript:

    do tx

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
        self.uxd_stack.value.serviceAllTx()
        self.udp_stack.value.serviceAllTx()


class Router(ioflo.base.deeding.Deed):
    '''
    Routes the communication in and out of uxd connections

    This is the initial static salt router, we want to create a dynamic
    router that takes a map that defines where packets are send
    FloScript:

    do router

    '''
    Ioinits = {'opts': '.salt.opts',
               'local_cmd': '.salt.var.local_cmd',
               'remote_cmd': '.salt.var.remote_cmd',
               'publish': '.salt.var.publish',
               'fun': '.salt.var.fun',
               'event': '.salt.event.events',
               'event_req': '.salt.event.event_req',
               'workers': '.salt.track.workers',
               'worker_verify': '.salt.var.worker_verify',
               'uxd_stack': '.salt.uxd.stack.stack',
               'udp_stack': '.raet.udp.stack.stack'}

    def _process_udp_rxmsg(self, msg, sender):
        '''
        Send to the right queue
        msg is the message body dict
        sender is the unique name of the remote estate that sent the message
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
        elif d_estate != self.udp_stack.value.local.name:
            log.error(
                    'Received message for wrong estate: {0}'.format(d_estate))
            return
        if d_yard is not None:
            # Meant for another yard, send it off!
            if d_yard in self.uxd_stack.value.nameRemotes:
                self.uxd_stack.value.transmit(msg,
                        self.uxd_stack.value.nameRemotes[d_yard].uid)
                return
            return
        if d_share is None:
            # No queue destination!
            log.error('Received message without share: {0}'.format(msg))
            return
        elif d_share == 'local_cmd':
            # Refuse local commands over the wire
            log.error('Received local command remotely! Ignoring: {0}'.format(msg))
            return
        elif d_share == 'remote_cmd':
            # Send it to a remote worker
            if 'load' in msg:
                msg['load']['id'] = sender
                self.uxd_stack.value.transmit(msg,
                        self.uxd_stack.value.fetchUidByName(next(self.workers.value)))
        elif d_share == 'fun':
            self.fun.value.append(msg)

    def _process_uxd_rxmsg(self, msg, sender):
        '''
        Send uxd messages tot he right queue or forward them to the correct
        yard etc.

        msg is message body dict
        sender is unique name  of remote that sent the message
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
        elif d_estate != self.udp_stack.value.local:
            # Forward to the correct estate
            eid = self.udp_stack.value.fetchUidByName(d_estate)
            self.udp_stack.value.message(msg, eid)
            return
        if d_share == 'pub_ret':
            if msg.get('__worker_verify') == self.worker_verify.value:
                self.publish.value.append(msg)
        if d_yard is None:
            pass
        elif d_yard != self.uxd_stack.value.local.name:
            # Meant for another yard, send it off!
            if d_yard in self.uxd_stack.value.nameRemotes:
                self.uxd_stack.value.transmit(msg,
                        self.uxd_stack.value.nameRemotes[d_yard].uid)
                return
            return
        if d_share is None:
            # No queue destination!
            log.error('Received message without share: {0}'.format(msg))
            return
        elif d_share == 'local_cmd':
            self.uxd_stack.value.transmit(msg,
                    self.uxd_stack.value.fetchUidByName(next(self.workers.value)))
        elif d_share == 'event_req':
            self.event_req.value.append(msg)
        elif d_share == 'event_fire':
            self.event.value.append(msg)

    def action(self):
        '''
        Process the messages!
        '''
        while self.udp_stack.value.rxMsgs:
            msg, sender = self.udp_stack.value.rxMsgs.popleft()
            self._process_udp_rxmsg(msg=msg, sender=sender)
        while self.uxd_stack.value.rxMsgs:
            msg, sender = self.uxd_stack.value.rxMsgs.popleft()
            self._process_uxd_rxmsg(msg=msg, sender=sender)


class Eventer(ioflo.base.deeding.Deed):
    '''
    Fire events!
    FloScript:

    do eventer

    '''
    Ioinits = {'opts': '.salt.opts',
               'event_yards': '.salt.event.yards',
               'event': '.salt.event.events',
               'event_req': '.salt.event.event_req',
               'module_refresh': '.salt.var.module_refresh',
               'pillar_refresh': '.salt.var.pillar_refresh',
               'uxd_stack': '.salt.uxd.stack.stack'}

    def _register_event_yard(self, msg):
        '''
        register an incoming event request with the requesting yard id
        '''
        self.event_yards.value.add(msg['route']['src'][1])

    def _fire_event(self, event):
        '''
        Fire an event to all subscribed yards
        '''
        rm_ = []
        if event.get('tag') == 'pillar_refresh':
            self.pillar_refresh.value = True
        if event.get('tag') == 'module_refresh':
            self.module_refresh.value = True
        for y_name in self.event_yards.value:
            if y_name not in self.uxd_stack.value.nameRemotes:
                rm_.append(y_name)
                continue
            route = {'src': ('router', self.uxd_stack.value.local.name, None),
                     'dst': ('router', y_name, None)}
            msg = {'route': route, 'event': event}
            self.uxd_stack.value.transmit(msg,
                    self.uxd_stack.value.fetchUidByName(y_name))
            self.uxd_stack.value.serviceAll()
        for y_name in rm_:
            self.event_yards.value.remove(y_name)

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


class SaltPublisher(ioflo.base.deeding.Deed):
    '''
    Publish to the minions
    FloScript:

    do salt publisher

    '''
    Ioinits = {'opts': '.salt.opts',
               'publish': '.salt.var.publish',
               'stack': '.raet.udp.stack.stack',
               'availables': {'ipath': '.salt.var.presence.availables',
                              'ival': set()}, }

    def _publish(self, pub_msg):
        '''
        Publish the message out to the targeted minions
        '''
        pub_data = pub_msg['return']
        # only publish to available minions by intersecting sets
        minions = self.availables.value & set(self.stack.value.nameRemotes.keys())
        for minion in minions:
            eid = self.stack.value.fetchUidByName(minion)
            if eid:
                route = {
                        'dst': (minion, None, 'fun'),
                        'src': (self.stack.value.local.name, None, None)}
                msg = {'route': route, 'pub': pub_data['pub']}
                self.stack.value.message(msg, eid)

    def action(self):
        '''
        Pop the publish queue and publish the requests!
        '''
        while self.publish.value:
            self._publish(
                    self.publish.value.popleft()
                    )


class NixExecutor(ioflo.base.deeding.Deed):
    '''
    Execute a function call on a *nix based system
    FloScript:

    do nix executor

    '''
    Ioinits = {'opts_store': '.salt.opts',
               'grains': '.salt.grains',
               'modules': '.salt.loader.modules',
               'returners': '.salt.loader.returners',
               'fun': '.salt.var.fun',
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

    def _setup_jobber_stack(self):
        '''
        Setup and return the LaneStack and Yard used by the jobber to communicate to-from
        the minion

        '''
        mid = self.opts['id']
        yid = nacling.uuid(size=18)
        name = 'jobber' + yid
        stack = LaneStack(
                name=name,
                lanename=mid,
                sockdirpath=self.opts['sock_dir'])

        stack.Pk = raeting.packKinds.pack
        stack.addRemote(RemoteYard(stack=stack,
                                   name='manor',
                                   lanename=mid,
                                   dirpath=self.opts['sock_dir']))
        console.concise("Created Jobber Stack {0}\n".format(stack.name))
        return stack

    def _return_pub(self, msg, ret, stack):
        '''
        Send the return data back via the uxd socket
        '''
        mid = self.opts['id']
        route = {'src': (mid, stack.local.name, 'jid_ret'),
                         'dst': (msg['route']['src'][0], None, 'remote_cmd')}
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
            exchange = self.fun.value.popleft()
            data = exchange.get('pub')
            match = getattr(
                    self.matcher,
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

        salt.transport.jobber_stack = stack = self._setup_jobber_stack()

        sdata = {'pid': os.getpid()}
        sdata.update(data)
        with salt.utils.fopen(fn_, 'w+') as fp_:
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
        self._return_pub(exchange, ret, stack)
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
