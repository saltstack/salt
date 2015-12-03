# -*- coding: utf-8 -*-
'''
The core behaviors used by minion and master
'''
# pylint: disable=W0232

# Import python libs
from __future__ import absolute_import
import os
import time
import random
import logging
import itertools
from collections import deque
from _socket import gaierror

# Import salt libs
import salt.daemons.masterapi
import salt.utils.args
import salt.utils.process
import salt.transport
import salt.engines
from raet import raeting
from raet.road.stacking import RoadStack
from raet.road.estating import RemoteEstate
from raet.lane.stacking import LaneStack

from salt import daemons
from salt.daemons import salting
from salt.exceptions import SaltException
from salt.utils import kinds, is_windows
from salt.utils.event import tagify

# Import ioflo libs

from ioflo.aid.odicting import odict  # pylint: disable=E0611,F0401
import ioflo.base.deeding
from ioflo.base.consoling import getConsole
console = getConsole()

# Import Third Party Libs
# pylint: disable=import-error
HAS_PSUTIL = False
try:
    import salt.utils.psutil_compat as psutil
    HAS_PSUTIL = True
except ImportError:
    pass

HAS_RESOURCE = False
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    pass
# pylint: disable=no-name-in-module,redefined-builtin
import salt.ext.six as six
from salt.ext.six.moves import range
# pylint: enable=import-error,no-name-in-module,redefined-builtin

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
        if not is_windows() and self.opts.value.get('sock_dir'):
            sockdirpath = os.path.abspath(self.opts.value['sock_dir'])
            console.concise("Cleaning up uxd files in {0}\n".format(sockdirpath))
            protecteds = self.opts.value.get('raet_cleanup_protecteds', [])
            for name in os.listdir(sockdirpath):
                path = os.path.join(sockdirpath, name)
                if os.path.isdir(path):
                    continue
                root, ext = os.path.splitext(name)
                if ext != '.uxd':
                    continue
                if not all(root.partition('.')):
                    continue
                if path in protecteds:
                    continue
                try:
                    os.unlink(path)
                    console.concise("Removed {0}\n".format(path))
                except OSError:
                    console.concise("Failed removing {0}\n".format(path))
                    raise


class SaltRaetRoadClustered(ioflo.base.deeding.Deed):
    '''
    Updates value of share .salt.road.manor.cluster.clustered
    Twith opts['cluster_mode']

    FloScript:

    do salt raet road clustered
    go next if .salt.road.manor.cluster.clustered

    '''
    Ioinits = odict(inode=".salt.road.manor.",
                    clustered=odict(ipath='cluster.clustered', ival=False),
                    opts='.salt.opts',)

    def action(self, **kwa):
        '''
        Update .cluster.clustered share from opts
        '''
        self.clustered.update(value=self.opts.value.get('cluster_mode', False))


class SaltRaetProcessManagerSetup(ioflo.base.deeding.Deed):
    '''
    Set up the process manager object
    '''
    Ioinits = {'proc_mgr': '.salt.usr.proc_mgr'}

    def action(self):
        '''
        Create the process manager
        '''
        self.proc_mgr.value = salt.utils.process.ProcessManager()


class SaltRaetRoadUsherMinionSetup(ioflo.base.deeding.Deed):
    '''
    Set up .ushers which is initial list of masters to bootstrap
    into road

    FloScript:

    do salt raet road usher minion setup at enter

    '''
    Ioinits = odict(
        inode=".salt.road.manor.",
        ushers='ushers',
        opts='.salt.opts')

    def action(self):
        '''
        Assign .ushers by parsing opts
        '''
        masters = 'master'
        port = None
        if self.opts.value.get('cluster_mode', False):
            masters = 'cluster_masters'

        self.ushers.value = daemons.extract_masters(self.opts.value,
                                                    masters=masters,
                                                    port=port)


class SaltRaetRoadUsherMasterSetup(ioflo.base.deeding.Deed):
    '''
    Set up .ushers which is initial list of masters to bootstrap
    into road

    FloScript:

    do salt raet road usher master setup at enter

    '''
    Ioinits = odict(
        inode=".salt.road.manor.",
        ushers='ushers',
        opts='.salt.opts')

    def action(self):
        '''
        Assign .ushers by parsing opts
        '''
        masters = 'cluster_masters'
        port = 'raet_port'

        self.ushers.value = daemons.extract_masters(self.opts.value,
                                                    masters=masters,
                                                    port=port,
                                                    raise_if_empty=False)


class SaltRaetRoadClusterLoadSetup(ioflo.base.deeding.Deed):
    '''
    Sets up cluster.masters for load balancing

    FloScript:

    do salt raet road cluster load setup at enter

    '''
    Ioinits = odict(
        inode='.salt.road.manor.',
        masters={'ipath': 'cluster.masters', 'ival': odict()},
        stack='stack',
        opts='.salt.opts',)

    def action(self, **kwa):
        '''
        Populate loads from masters in stack.remotes
        '''
        if self.opts.value.get('cluster_mode'):
            for remote in list(self.stack.value.remotes.values()):
                if remote.kind == kinds.applKinds.master:
                    self.masters.value[remote.name] = odict(load=0.0, expire=self.store.stamp)


class SaltRaetRoadStackSetup(ioflo.base.deeding.Deed):
    '''
    Initialize and run raet udp stack for Salt
    FloScript:

    do salt raet road stack setup at enter

    '''
    Ioinits = {
            'inode': 'salt.road.manor.',
            'stack': 'stack',
            'opts': '.salt.opts',
            'txmsgs': {'ipath': 'txmsgs',
                       'ival': deque()},
            'rxmsgs': {'ipath': 'rxmsgs',
                       'ival': deque()},
            'local': {'ipath': 'local',
                      'ival': {'main': False,
                               'mutable': False,
                               'uid': None,
                               'role': 'master',
                               'sighex': None,
                               'prihex': None,
                               'bufcnt': 2}},
            }

    def _prepare(self):
        '''
        Assign class defaults
        '''
        RoadStack.Bk = raeting.BodyKind.msgpack.value
        RoadStack.JoinentTimeout = 0.0

    def action(self):
        '''
        enter action
        should only run once to setup road stack.
        moved from _prepare so can do clean up before stack is initialized

        do salt raet road stack setup at enter
        '''
        kind = self.opts.value['__role']  # application kind
        if kind not in kinds.APPL_KINDS:
            emsg = ("Invalid application kind = '{0}'.".format(kind))
            log.error(emsg + '\n')
            raise ValueError(emsg)
        role = self.opts.value.get('id', '')
        if not role:
            emsg = ("Missing role required to setup RoadStack.")
            log.error(emsg + "\n")
            raise ValueError(emsg)

        name = "{0}_{1}".format(role, kind)
        main = self.opts.value.get('raet_main', self.local.data.main)
        mutable = self.opts.value.get('raet_mutable', self.local.data.mutable)
        always = self.opts.value.get('open_mode', False)
        mutable = mutable or always  # open_made when True takes precedence
        uid = self.local.data.uid

        if kind == kinds.APPL_KIND_NAMES[kinds.applKinds.caller]:
            ha = (self.opts.value['interface'], self.opts.value['raet_alt_port'])
        else:
            ha = (self.opts.value['interface'], self.opts.value['raet_port'])

        basedirpath = os.path.abspath(os.path.join(self.opts.value['cachedir'], 'raet'))

        txMsgs = self.txmsgs.value
        rxMsgs = self.rxmsgs.value

        keep = salting.SaltKeep(opts=self.opts.value,
                                basedirpath=basedirpath,
                                stackname=name)

        roledata = keep.loadLocalRoleData()
        sighex = roledata['sighex'] or self.local.data.sighex
        prihex = roledata['prihex'] or self.local.data.prihex

        bufcnt = self.opts.value.get('raet_road_bufcnt', self.local.data.bufcnt)

        self.stack.value = RoadStack(store=self.store,
                                     keep=keep,
                                     name=name,
                                     uid=uid,
                                     ha=ha,
                                     role=role,
                                     sigkey=sighex,
                                     prikey=prihex,
                                     main=main,
                                     kind=kinds.APPL_KINDS[kind],
                                     mutable=mutable,
                                     txMsgs=txMsgs,
                                     rxMsgs=rxMsgs,
                                     period=3.0,
                                     offset=0.5,
                                     bufcnt=bufcnt)

        if self.opts.value.get('raet_clear_remotes'):
            for remote in list(self.stack.value.remotes.values()):
                self.stack.value.removeRemote(remote, clear=True)
            self.stack.puid = self.stack.value.Uid  # reset puid


class SaltRaetRoadStackCloser(ioflo.base.deeding.Deed):
    '''
    Closes stack server socket connection
    FloScript:

    do salt raet road stack closer at exit

    '''
    Ioinits = odict(
        inode=".salt.road.manor.",
        stack='stack', )

    def action(self, **kwa):
        '''
        Close udp socket
        '''
        if self.stack.value and isinstance(self.stack.value, RoadStack):
            self.stack.value.server.close()


class SaltRaetRoadStackJoiner(ioflo.base.deeding.Deed):
    '''
    Initiates join transaction with master(s)
    FloScript:

    do salt raet road stack joiner at enter

    assumes that prior the following has been run to setup .masters

    do salt raet road usher minion setup

    '''
    Ioinits = odict(
                    inode=".salt.road.manor.",
                    stack='stack',
                    ushers='ushers',
                    opts='.salt.opts')

    def action(self, **kwa):
        '''
        Join with all masters
        '''
        stack = self.stack.value
        if stack and isinstance(stack, RoadStack):
            refresh_masters = (self.opts.value.get('raet_clear_remote_masters',
                                       True) or not stack.remotes)

            refresh_all = (self.opts.value.get('raet_clear_remotes', True) or
                       not stack.remotes)

            if refresh_masters:  # clear all remote masters
                for remote in list(stack.remotes.values()):
                    if remote.kind == kinds.applKinds.master:
                        stack.removeRemote(remote, clear=True)

            if refresh_all:  # clear all remotes
                for remote in list(stack.remotes.values()):
                    stack.removeRemote(remote, clear=True)

            if refresh_all or refresh_masters:
                stack.puid = stack.Uid  # reset puid so reuse same uid each time

                ex = SaltException('Unable to connect to any master')
                for master in self.ushers.value:
                    try:
                        mha = master['external']
                        stack.addRemote(RemoteEstate(stack=stack,
                                                     fuid=0,  # vacuous join
                                                     sid=0,  # always 0 for join
                                                     ha=mha,
                                                     kind=kinds.applKinds.master))
                    except gaierror as ex:
                        log.warning("Unable to connect to master {0}: {1}".format(mha, ex))
                        if self.opts.value.get('master_type') != 'failover':
                            raise ex
                if not stack.remotes:
                    raise ex

            for remote in list(stack.remotes.values()):
                if remote.kind == kinds.applKinds.master:
                    stack.join(uid=remote.uid, timeout=0.0)


class SaltRaetRoadStackJoined(ioflo.base.deeding.Deed):
    '''
    Updates status with .joined of zeroth remote estate (master)
    FloScript:

    do salt raet road stack joined
    go next if joined in .salt.road.manor.status

    '''
    Ioinits = odict(
        inode=".salt.road.manor.",
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
                joined = any([remote.joined for remote in list(stack.remotes.values())
                              if remote.kind == kinds.applKinds.master])
        self.status.update(joined=joined)


class SaltRaetRoadStackRejected(ioflo.base.deeding.Deed):
    '''
    Updates status with rejected of .acceptance of zeroth remote estate (master)
    FloScript:

    do salt raet road stack rejected
    go next if rejected in .salt.road.manor.status

    '''
    Ioinits = odict(
        inode=".salt.road.manor.",
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
                rejected = all([remote.acceptance == raeting.Acceptance.rejected.value
                                for remote in stack.remotes.values()
                                if remote.kind == kinds.applKinds.master])
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
        inode=".salt.road.manor.",
        stack='stack', )

    def action(self, **kwa):
        '''
        Receive any udp packets on server socket and put in rxes
        Send any packets in txes
        '''
        stack = self.stack.value
        if stack and isinstance(stack, RoadStack):
            for remote in stack.remotes.values():
                if remote.kind == kinds.applKinds.master:
                    stack.allow(uid=remote.uid, timeout=0.0)


class SaltRaetRoadStackAllowed(ioflo.base.deeding.Deed):
    '''
    Updates status with .allowed of zeroth remote estate (master)
    FloScript:

    do salt raet road stack allowed
    go next if allowed in .salt.road.manor.status

    '''
    Ioinits = odict(
        inode=".salt.road.manor.",
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
                allowed = any([remote.allowed for remote in list(stack.remotes.values())
                               if remote.kind == kinds.applKinds.master])
        self.status.update(allowed=allowed)


class SaltRaetRoadStackManager(ioflo.base.deeding.Deed):
    '''
    Runs the manage method of RoadStack
    FloScript:
        do salt raet road stack manager

    '''
    Ioinits = odict(
        inode=".salt.road.manor.",
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
                  'ival': odict(plus=set(), minus=set())},
        event='.salt.event.events',)

    def _fire_events(self):
        stack = self.stack.value
        if self.changeds.data.plus or self.changeds.data.minus:
            # fire presence change event
            data = {'new': list(self.changeds.data.plus),
                    'lost': list(self.changeds.data.minus)}
            tag = tagify('change', 'presence')
            route = {'dst': (None, None, 'event_fire'),
                     'src': (None, stack.local.name, None)}
            msg = {'route': route, 'tag': tag, 'data': data}
            self.event.value.append(msg)
        # fire presence present event
        data = {'present': list(self.aliveds.value)}
        tag = tagify('present', 'presence')
        route = {'dst': (None, None, 'event_fire'),
                 'src': (None, stack.local.name, None)}
        msg = {'route': route, 'tag': tag, 'data': data}
        self.event.value.append(msg)

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

            self._fire_events()


class SaltRaetRoadStackPrinter(ioflo.base.deeding.Deed):
    '''
    Prints out messages on rxMsgs queue for associated stack
    FloScript:

    do raet road stack printer

    '''
    Ioinits = odict(
        inode=".salt.road.manor.",
        rxmsgs=odict(ipath='rxmsgs', ival=deque()),)

    def action(self, **kwa):
        '''
        Queue up message
        '''
        rxMsgs = self.rxmsgs.value
        while rxMsgs:
            msg, name = rxMsgs.popleft()
            console.terse("\nReceived....\n{0}\n".format(msg))


class SaltLoadModules(ioflo.base.deeding.Deed):
    '''
    Reload the minion modules
    FloScript:

    do salt load modules at enter

    '''
    Ioinits = {'opts': '.salt.opts',
               'grains': '.salt.grains',
               'utils': '.salt.loader.utils',
               'modules': '.salt.loader.modules',
               'grain_time': '.salt.var.grain_time',
               'module_refresh': '.salt.var.module_refresh',
               'returners': '.salt.loader.returners'}

    def _prepare(self):
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
            rss, vms = psutil.Process(os.getpid()).memory_info()
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
        self.utils.value = salt.loader.utils(self.opts.value)
        self.modules.value = salt.loader.minion_mods(self.opts.value, utils=self.utils.value)
        self.returners.value = salt.loader.returners(self.opts.value, self.modules.value)

        self.utils.value.clear()
        self.modules.value.clear()
        self.returners.value.clear()

        # we're done, reset the limits!
        if modules_max_memory is True:
            resource.setrlimit(resource.RLIMIT_AS, old_mem_limit)
        self.module_refresh.value = False


class SaltLoadPillar(ioflo.base.deeding.Deed):
    '''
    Load up the initial pillar for the minion

    do salt load pillar
    '''
    Ioinits = {'opts': '.salt.opts',
               'pillar': '.salt.pillar',
               'grains': '.salt.grains',
               'modules': '.salt.loader.modules',
               'pillar_refresh': '.salt.var.pillar_refresh',
               'road_stack': '.salt.road.manor.stack',
               'master_estate_name': '.salt.track.master_estate_name', }

    def action(self):
        '''
        Initial pillar
        '''
        # default master is the first remote that is allowed
        available_masters = [remote for remote in list(self.road_stack.value.remotes.values())
                                               if remote.allowed]
        while not available_masters:
            available_masters = [remote for remote in self.road_stack.value.remotes.values()
                                                           if remote.allowed]
            time.sleep(0.1)

        random_master = self.opts.value.get('random_master')
        if random_master:
            master = available_masters[random.randint(0, len(available_masters) - 1)]
        else:
            master = available_masters[0]

        self.master_estate_name.value = master.name

        route = {'src': (self.road_stack.value.local.name, None, None),
                 'dst': (master.name, None, 'remote_cmd')}
        load = {'id': self.opts.value['id'],
                'grains': self.grains.value,
                'saltenv': self.opts.value['environment'],
                'ver': '2',
                'cmd': '_pillar'}
        self.road_stack.value.transmit({'route': route, 'load': load},
                                       uid=master.uid)
        self.road_stack.value.serviceAll()
        while True:
            time.sleep(0.1)
            while self.road_stack.value.rxMsgs:
                msg, sender = self.road_stack.value.rxMsgs.popleft()
                self.pillar.value = msg.get('return', {})
                if self.pillar.value is None:
                    continue
                self.opts.value['pillar'] = self.pillar.value
                self.pillar_refresh.value = False
                return
            self.road_stack.value.serviceAll()


class SaltSchedule(ioflo.base.deeding.Deed):
    '''
    Evaluates the schedule
    FloScript:

    do salt schedule

    '''
    Ioinits = {'opts': '.salt.opts',
               'grains': '.salt.grains',
               'utils': '.salt.loader.utils',
               'modules': '.salt.loader.modules',
               'returners': '.salt.loader.returners'}

    def _prepare(self):
        '''
        Map opts and make the schedule object
        '''
        self.utils.value = salt.loader.utils(self.opts.value)
        self.modules.value = salt.loader.minion_mods(self.opts.value, utils=self.utils.value)
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


class SaltRaetManorLaneSetup(ioflo.base.deeding.Deed):
    '''
    Only intended to be called once at the top of the manor house
    Sets up the LaneStack for the main yard
    FloScript:

    do salt raet manor lane setup at enter

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
               'presence_req': '.salt.presence.event_req',
               'stats_req': '.salt.stats.event_req',
               'workers': '.salt.track.workers',
               'inode': '.salt.lane.manor.',
               'stack': 'stack',
               'local': {'ipath': 'local',
                          'ival': {'lanename': 'master',
                                   'bufcnt': 100}},
            }

    def _prepare(self):
        '''
        Set up required objects and queues
        '''
        pass

    def action(self):
        '''
        Run once at enter
        '''
        kind = self.opts.value['__role']
        if kind not in kinds.APPL_KINDS:
            emsg = ("Invalid application kind = '{0}' for manor lane.".format(kind))
            log.error(emsg + "\n")
            raise ValueError(emsg)

        if kind in [kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                    kinds.APPL_KIND_NAMES[kinds.applKinds.syndic]]:
            lanename = 'master'
        elif kind in [kinds.APPL_KIND_NAMES[kinds.applKinds.minion],
                      kinds.APPL_KIND_NAMES[kinds.applKinds.caller], ]:
            role = self.opts.value.get('id', '')
            if not role:
                emsg = ("Missing role required to setup manor Lane.")
                log.error(emsg + "\n")
                raise ValueError(emsg)
            lanename = "{0}_{1}".format(role, kind)
        else:
            emsg = ("Unsupported application kind = '{0}' for manor Lane.".format(kind))
            log.error(emsg + '\n')
            raise ValueError(emsg)

        bufcnt = self.opts.value.get('raet_lane_bufcnt', self.local.data.bufcnt)

        name = 'manor'
        self.stack.value = LaneStack(
                                    name=name,
                                    lanename=lanename,
                                    sockdirpath=self.opts.value['sock_dir'],
                                    bufcnt=bufcnt)
        self.stack.value.Pk = raeting.PackKind.pack.value
        self.event_yards.value = set()
        self.local_cmd.value = deque()
        self.remote_cmd.value = deque()
        self.fun.value = deque()
        self.event.value = deque()
        self.event_req.value = deque()
        self.presence_req.value = deque()
        self.stats_req.value = deque()
        self.publish.value = deque()
        self.worker_verify.value = salt.utils.rand_string()
        if self.opts.value.get('worker_threads'):
            worker_seed = []
            for index in range(self.opts.value['worker_threads']):
                worker_seed.append('worker{0}'.format(index + 1))
            self.workers.value = itertools.cycle(worker_seed)


class SaltRaetLaneStackCloser(ioflo.base.deeding.Deed):  # pylint: disable=W0232
    '''
    Closes lane stack server socket connection
    FloScript:

    do raet lane stack closer at exit

    '''
    Ioinits = odict(
        inode=".salt.lane.manor",
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
               'road_stack': '.salt.road.manor.stack',
               }

    def action(self):
        '''
        Process inboud queues
        '''
        self.road_stack.value.serviceAll()


class SaltRaetRoadStackServiceRx(ioflo.base.deeding.Deed):
    '''
    Process the inbound Road traffic
    FloScript:

    do salt raet road stack service rx

    '''
    Ioinits = {
               'road_stack': '.salt.road.manor.stack',
               }

    def action(self):
        '''
        Process inboud queues
        '''
        self.road_stack.value.serviceAllRx()


class SaltRaetRoadStackServiceTx(ioflo.base.deeding.Deed):
    '''
    Process the outbound Road traffic
    FloScript:

    do salt raet road stack service tx

    '''
    # Yes, this class is identical to RX, this is because we still need to
    # separate out rx and tx in raet itself
    Ioinits = {
               'road_stack': '.salt.road.manor.stack',
               }

    def action(self):
        '''
        Process inbound queues
        '''
        self.road_stack.value.serviceAllTx()


class SaltRaetLaneStackServiceRx(ioflo.base.deeding.Deed):
    '''
    Process the inbound Lane traffic
    FloScript:

    do salt raet lane stack service rx

    '''
    Ioinits = {
               'lane_stack': '.salt.lane.manor.stack',
               }

    def action(self):
        '''
        Process inboud queues
        '''
        self.lane_stack.value.serviceAllRx()


class SaltRaetLaneStackServiceTx(ioflo.base.deeding.Deed):
    '''
    Process the outbound Lane traffic
    FloScript:

    do salt raet lane stack service tx

    '''
    # Yes, this class is identical to RX, this is because we still need to
    # separate out rx and tx in raet itself
    Ioinits = {
               'lane_stack': '.salt.lane.manor.stack',
               }

    def action(self):
        '''
        Process outbound queues
        '''
        self.lane_stack.value.serviceAllTx()


class SaltRaetRouter(ioflo.base.deeding.Deed):
    '''
    Routes the communication in and out of Road and Lane connections

    This is a base class

    '''
    Ioinits = {'opts': '.salt.opts',
               'local_cmd': '.salt.var.local_cmd',
               'remote_cmd': '.salt.var.remote_cmd',
               'publish': '.salt.var.publish',
               'fun': '.salt.var.fun',
               'event': '.salt.event.events',
               'event_req': '.salt.event.event_req',  # deque
               'presence_req': '.salt.presence.event_req',  # deque
               'stats_req': '.salt.stats.event_req',  # deque
               'availables': '.salt.var.presence.availables',  # set()
               'workers': '.salt.track.workers',
               'worker_verify': '.salt.var.worker_verify',
               'lane_stack': '.salt.lane.manor.stack',
               'road_stack': '.salt.road.manor.stack',
               'master_estate_name': '.salt.track.master_estate_name',
               'laters': {'ipath': '.salt.lane.manor.laters',  # requeuing when not yet routable
                          'ival': deque()}}

    def _process_road_rxmsg(self, msg, sender):
        '''
        Send to the right queue
        msg is the message body dict
        sender is the unique name of the remote estate that sent the message
        '''
        pass

    def _process_lane_rxmsg(self, msg, sender):
        '''
        Send uxd messages tot he right queue or forward them to the correct
        yard etc.

        msg is message body dict
        sender is unique name  of remote that sent the message
        '''
        pass

    def _get_master_estate_name(self, clustered=False):
        '''
        Assign and return the name of the estate for the default master or empty if none
        If the default master is no longer available then selects one of the available
        masters

        If clustered is True then use load balancing algorithm to select master
        '''
        opts = self.opts.value
        master = self.road_stack.value.nameRemotes.get(self.master_estate_name.value)
        if not master or not master.alived:  # select a different master
            available_masters = [remote for remote in
                                 six.Iterator(self.road_stack.value.remotes)
                                                       if remote.alived]
            if available_masters:
                random_master = opts.get('random_master')
                if random_master:
                    master = available_masters[random.randint(0, len(available_masters) - 1)]
                else:
                    master = available_masters[0]
            else:
                master = None

        self.master_estate_name.value = master.name if master else ''

        return self.master_estate_name.value

    def _availablize(self, minions):
        '''
        Return set that is intersection of associated minion estates for
        roles in minions and the set of available minion estates.
        '''
        suffix = '_{0}'.format(kinds.APPL_KIND_NAMES[kinds.applKinds.minion])
        return list(set(minions) &
                    set((name.rstrip(suffix) for name in self.availables.value)))

    def action(self):
        '''
        Process the messages!
        '''
        while self.road_stack.value.rxMsgs:
            msg, sender = self.road_stack.value.rxMsgs.popleft()
            self._process_road_rxmsg(msg=msg, sender=sender)
        while self.laters.value:  # process requeued LaneMsgs
            msg, sender = self.laters.value.popleft()
            self.lane_stack.value.rxMsgs.append((msg, sender))
        while self.lane_stack.value.rxMsgs:
            msg, sender = self.lane_stack.value.rxMsgs.popleft()
            self._process_lane_rxmsg(msg=msg, sender=sender)


class SaltRaetRouterMaster(SaltRaetRouter):
    '''
    Routes the communication in and out of Road and Lane connections
    Specific to Master

    do salt raet router master

    '''
    def _process_road_rxmsg(self, msg, sender):
        '''
        Send to the right queue
        msg is the message body dict
        sender is the unique name of the remote estate that sent the message
        '''
        try:
            s_estate, s_yard, s_share = msg['route']['src']
            d_estate, d_yard, d_share = msg['route']['dst']
        except (ValueError, IndexError):
            log.error('Received invalid message: {0}'.format(msg))
            return

        if s_estate is None:  # drop
            return

        log.debug("**** Road Router rxMsg **** id={0} estate={1} yard={2}\n"
                  "   msg= {3}\n".format(
                      self.opts.value['id'],
                      self.road_stack.value.local.name,
                      self.lane_stack.value.local.name,
                      msg))

        if d_estate is not None and d_estate != self.road_stack.value.local.name:
            log.error(
                'Road Router Received message for wrong estate: {0}'.format(d_estate))
            return

        if d_yard is not None:
            # Meant for another yard, send it off!
            if d_yard in self.lane_stack.value.nameRemotes:
                self.lane_stack.value.transmit(msg,
                                               self.lane_stack.value.nameRemotes[d_yard].uid)
            return
        if d_share is None:
            # No queue destination!
            log.error('Received message without share: {0}'.format(msg))
            return
        elif d_share == 'event_fire':  # rebroadcast events from other masters
            self.event.value.append(msg)
            #log.debug("\n**** Event Fire \n {0}\n".format(msg))
            return
        elif d_share == 'local_cmd':
            # Refuse local commands over the wire
            log.error('Received local command remotely! Ignoring: {0}'.format(msg))
            return
        elif d_share == 'remote_cmd':
            # Send it to a remote worker
            if 'load' in msg:
                role = self.road_stack.value.nameRemotes[sender].role
                msg['load']['id'] = role  # sender # should this be role XXXX
                self.lane_stack.value.transmit(msg,
                                               self.lane_stack.value.fetchUidByName(next(self.workers.value)))

    def _process_lane_rxmsg(self, msg, sender):
        '''
        Send uxd messages tot he right queue or forward them to the correct
        yard etc.

        msg is message body dict
        sender is unique name  of remote that sent the message
        '''
        try:
            s_estate, s_yard, s_share = msg['route']['src']
            d_estate, d_yard, d_share = msg['route']['dst']
        except (ValueError, IndexError):
            log.error('Lane Router Received invalid message: {0}'.format(msg))
            return

        if s_yard is None:
            return  # drop message

        if s_estate is None:  # substitute local estate
            s_estate = self.road_stack.value.local.name
            msg['route']['src'] = (s_estate, s_yard, s_share)

        log.debug("**** Lane Router rxMsg **** id={0} estate={1} yard={2}\n"
                  "   msg={3}\n".format(
                      self.opts.value['id'],
                      self.road_stack.value.local.name,
                      self.lane_stack.value.local.name,
                      msg))

        if d_estate is None:
            pass
        elif d_estate != self.road_stack.value.local.name:
            # Forward to the correct estate
            if d_estate in self.road_stack.value.nameRemotes:
                self.road_stack.value.message(msg,
                                              self.road_stack.value.nameRemotes[d_estate].uid)
            return

        if d_share == 'pub_ret':
            # only publish to available minions
            msg['return']['ret']['minions'] = self._availablize(msg['return']['ret']['minions'])
            if msg.get('__worker_verify') == self.worker_verify.value:
                self.publish.value.append(msg)

        if d_yard is None:
            pass
        elif d_yard != self.lane_stack.value.local.name:
            # Meant for another yard, send it off!
            if d_yard in self.lane_stack.value.nameRemotes:
                self.lane_stack.value.transmit(msg,
                                               self.lane_stack.value.nameRemotes[d_yard].uid)
            return
        if d_share is None:
            # No queue destination!
            log.error('Lane Router Received message without share: {0}'.format(msg))
            return
        elif d_share == 'local_cmd':
            self.lane_stack.value.transmit(msg,
                                           self.lane_stack.value.fetchUidByName(next(self.workers.value)))
        elif d_share == 'event_req':
            self.event_req.value.append(msg)
            #log.debug("\n**** Event Subscribe \n {0}\n".format(msg))
        elif d_share == 'event_fire':
            self.event.value.append(msg)
            #log.debug("\n**** Event Fire \n {0}\n".format(msg))
        elif d_share == 'presence_req':
            self.presence_req.value.append(msg)
            #log.debug("\n**** Presence Request \n {0}\n".format(msg))
        elif d_share == 'stats_req':
            self.stats_req.value.append(msg)
            #log.debug("\n**** Stats Request \n {0}\n".format(msg))


class SaltRaetRouterMinion(SaltRaetRouter):
    '''
    Routes the communication in and out of Road and Lane connections
    Specific to Minions

    do salt raet router minion

    '''
    def _process_road_rxmsg(self, msg, sender):
        '''
        Send to the right queue
        msg is the message body dict
        sender is the unique name of the remote estate that sent the message
        '''
        try:
            s_estate, s_yard, s_share = msg['route']['src']
            d_estate, d_yard, d_share = msg['route']['dst']
        except (ValueError, IndexError):
            log.error('Received invalid message: {0}'.format(msg))
            return

        if s_estate is None:  # drop
            return

        log.debug("**** Road Router rxMsg **** id={0} estate={1} yard={2}\n"
                  "   msg= {3}\n".format(
                      self.opts.value['id'],
                      self.road_stack.value.local.name,
                      self.lane_stack.value.local.name,
                      msg))

        if d_estate is not None and d_estate != self.road_stack.value.local.name:
            log.error(
                'Road Router Received message for wrong estate: {0}'.format(d_estate))
            return

        if d_yard is not None:
            # Meant for another yard, send it off!
            if d_yard in self.lane_stack.value.nameRemotes:
                self.lane_stack.value.transmit(msg,
                                               self.lane_stack.value.nameRemotes[d_yard].uid)
                return
            return
        if d_share is None:
            # No queue destination!
            log.error('Received message without share: {0}'.format(msg))
            return

        elif d_share == 'fun':
            if self.road_stack.value.kind == kinds.applKinds.minion:
                self.fun.value.append(msg)
        elif d_share == 'stats_req':
            self.stats_req.value.append(msg)
            #log.debug("\n**** Stats Request \n {0}\n".format(msg))

    def _process_lane_rxmsg(self, msg, sender):
        '''
        Send uxd messages tot he right queue or forward them to the correct
        yard etc.

        msg is message body dict
        sender is unique name  of remote that sent the message
        '''
        try:
            s_estate, s_yard, s_share = msg['route']['src']
            d_estate, d_yard, d_share = msg['route']['dst']
        except (ValueError, IndexError):
            log.error('Lane Router Received invalid message: {0}'.format(msg))
            return

        if s_yard is None:
            return  # drop message

        if s_estate is None:  # substitute local estate
            s_estate = self.road_stack.value.local.name
            msg['route']['src'] = (s_estate, s_yard, s_share)

        log.debug("**** Lane Router rxMsg **** id={0} estate={1} yard={2}\n"
                  "   msg={3}\n".format(
                      self.opts.value['id'],
                      self.road_stack.value.local.name,
                      self.lane_stack.value.local.name,
                      msg))

        if d_estate is None:
            pass
        elif d_estate != self.road_stack.value.local.name:
            # Forward to the correct estate
            if d_estate in self.road_stack.value.nameRemotes:
                self.road_stack.value.message(msg,
                                              self.road_stack.value.nameRemotes[d_estate].uid)
            return

        if d_yard is None:
            pass
        elif d_yard != self.lane_stack.value.local.name:
            # Meant for another yard, send it off!
            if d_yard in self.lane_stack.value.nameRemotes:
                self.lane_stack.value.transmit(msg,
                                               self.lane_stack.value.nameRemotes[d_yard].uid)
                return
            return
        if d_share is None:
            # No queue destination!
            log.error('Lane Router Received message without share: {0}'.format(msg))
            return

        elif d_share == 'event_req':
            self.event_req.value.append(msg)
            #log.debug("\n**** Event Subscribe \n {0}\n".format(msg))
        elif d_share == 'event_fire':
            self.event.value.append(msg)
            #log.debug("\n**** Event Fire \n {0}\n".format(msg))

        elif d_share == 'remote_cmd':  # assume  minion to master or salt-call
            if not self.road_stack.value.remotes:
                log.error("**** Lane Router: Missing joined master. Unable to route "
                          "remote_cmd. Requeuing".format())
                self.laters.value.append((msg, sender))
                return
            d_estate = self._get_master_estate_name(clustered=self.opts.get('cluster_mode', False))
            if not d_estate:
                log.error("**** Lane Router: No available destination estate for 'remote_cmd'."
                          "Unable to route. Requeuing".format())
                self.laters.value.append((msg, sender))
                return
            msg['route']['dst'] = (d_estate, d_yard, d_share)
            log.debug("**** Lane Router: Missing destination estate for 'remote_cmd'. "
                      "Using default route={0}.".format(msg['route']['dst']))
            self.road_stack.value.message(msg,
                                          self.road_stack.value.nameRemotes[d_estate].uid)

    def _get_master_estate_name(self, clustered=False):
        '''
        Assign and return the name of the estate for the default master or empty if none
        If the default master is no longer available then selects one of the available
        masters
        '''
        opts = self.opts.value
        master = self.road_stack.value.nameRemotes.get(self.master_estate_name.value)
        if not master or not master.alived:  # select a different master
            available_masters = [remote for remote in
                                 list(self.road_stack.value.remotes.values())
                                                       if remote.alived]
            if available_masters:
                random_master = opts.get('random_master')
                if random_master:
                    master = available_masters[random.randint(0, len(available_masters) - 1)]
                else:
                    master = available_masters[0]
            else:
                master = None

        self.master_estate_name.value = master.name if master else ''

        return self.master_estate_name.value

    def _availablize(self, minions):
        '''
        Return set that is intersection of associated minion estates for
        roles in minions and the set of available minion estates.
        '''
        suffix = '_{0}'.format(kinds.APPL_KIND_NAMES[kinds.applKinds.minion])
        return list(set(minions) &
                    set((name.rstrip(suffix) for name in self.availables.value)))


class SaltRaetEventer(ioflo.base.deeding.Deed):
    '''
    Fire events!
    FloScript:

    do salt raet eventer

    '''
    Ioinits = {'opts': '.salt.opts',
               'event_yards': '.salt.event.yards',
               'event': '.salt.event.events',
               'event_req': '.salt.event.event_req',
               'module_refresh': '.salt.var.module_refresh',
               'pillar_refresh': '.salt.var.pillar_refresh',
               'lane_stack': '.salt.lane.manor.stack',
               'road_stack': '.salt.road.manor.stack',
               'availables': '.salt.var.presence.availables', }

    def _register_event_yard(self, msg):
        '''
        register an incoming event request with the requesting yard id
        '''
        self.event_yards.value.add(msg['route']['src'][1])

    def _forward_event(self, msg):
        '''
        Forward an event message to all subscribed yards
        Event message has a route
        '''
        rm_ = []
        if msg.get('tag') == 'pillar_refresh':
            self.pillar_refresh.value = True
        if msg.get('tag') == 'module_refresh':
            self.module_refresh.value = True
        for y_name in self.event_yards.value:
            if y_name not in self.lane_stack.value.nameRemotes:  # subscriber not a remote
                rm_.append(y_name)
                continue  # drop msg don't publish
            self.lane_stack.value.transmit(msg,
                    self.lane_stack.value.fetchUidByName(y_name))
            self.lane_stack.value.serviceAll()
        for y_name in rm_:  # remove missing subscribers
            self.event_yards.value.remove(y_name)

    def action(self):
        '''
        Register event requests
        Iterate over the registered event yards and fire!
        '''
        while self.event_req.value:  # event subscription requests are msg with routes
            self._register_event_yard(
                    self.event_req.value.popleft()
                    )

        while self.event.value:  # events are msgs with routes
            self._forward_event(
                    self.event.value.popleft()
                    )


class SaltRaetEventerMaster(SaltRaetEventer):
    '''
    Fire events!
    FloScript:

    do salt raet eventer master

    '''
    def _forward_event(self, msg):
        '''
        Forward an event message to all subscribed yards
        Event message has a route
        Also rebroadcast to all masters in cluster
        '''
        super(SaltRaetEventerMaster, self)._forward_event(msg)
        if self.opts.value.get('cluster_mode'):
            if msg.get('origin') is None:
                masters = (self.availables.value &
                           set((remote.name for remote in list(self.road_stack.value.remotes.values())
                                if remote.kind == kinds.applKinds.master)))
                for name in masters:
                    remote = self.road_stack.value.nameRemotes[name]
                    msg['origin'] = self.road_stack.value.name
                    s_estate, s_yard, s_share = msg['route']['src']
                    msg['route']['src'] = (self.road_stack.value.name, s_yard, s_share)
                    msg['route']['dst'] = (remote.name, None, 'event_fire')
                    self.road_stack.value.message(msg, remote.uid)


class SaltRaetPresenter(ioflo.base.deeding.Deed):
    '''
    Fire presence events!
    FloScript:

    do salt raet presenter

    '''
    Ioinits = {'opts': '.salt.opts',
               'presence_req': '.salt.presence.event_req',
               'lane_stack': '.salt.lane.manor.stack',
               'alloweds': '.salt.var.presence.alloweds',  # odict
               'aliveds': '.salt.var.presence.aliveds',  # odict
               'reapeds': '.salt.var.presence.reapeds',  # odict
               'availables': '.salt.var.presence.availables',  # set
              }

    def _send_presence(self, msg):
        '''
        Forward an presence message to all subscribed yards
        Presence message has a route
        '''
        y_name = msg['route']['src'][1]
        if y_name not in self.lane_stack.value.nameRemotes:  # subscriber not a remote
            pass  # drop msg don't answer
        else:
            if 'data' in msg and 'state' in msg['data']:
                state = msg['data']['state']
            else:
                state = None

            # create answer message
            if state in [None, 'available', 'present']:
                present = odict()
                for name in self.availables.value:
                    minion = self.aliveds.value.get(name, None)
                    present[name] = minion.ha[0] if minion else None
                data = {'present': present}
            else:
                # TODO: update to really return joineds
                states = {'joined': self.alloweds,
                          'allowed': self.alloweds,
                          'alived': self.aliveds,
                          'reaped': self.reapeds}
                try:
                    minions = states[state].value
                except KeyError:
                    # error: wrong/unknown state requested
                    log.error('Lane Router Received invalid message: {0}'.format(msg))
                    return

                result = odict()
                for name in minions:
                    result[name] = minions[name].ha[0]
                data = {state: result}

            tag = tagify('present', 'presence')
            route = {'dst': (None, None, 'event_fire'),
                     'src': (None, self.lane_stack.value.local.name, None)}
            msg = {'route': route, 'tag': tag, 'data': data}
            self.lane_stack.value.transmit(msg,
                                           self.lane_stack.value.fetchUidByName(y_name))
            self.lane_stack.value.serviceAll()

    def action(self):
        '''
        Register presence requests
        Iterate over the registered presence yards and fire!
        '''
        while self.presence_req.value:  # presence are msgs with routes
            self._send_presence(
                self.presence_req.value.popleft()
            )


class SaltRaetStatsEventer(ioflo.base.deeding.Deed):
    '''
    Fire stats events
    FloScript:

    do salt raet state eventer

    '''
    Ioinits = {'opts': '.salt.opts',
               'stats_req': '.salt.stats.event_req',
               'lane_stack': '.salt.lane.manor.stack',
               'road_stack': '.salt.road.manor.stack',
    }

    def _send_stats(self, msg):
        '''
        Forward a stats message to all subscribed yards
        Stats message has a route
        '''
        pass

    def _get_stats(self, tag):
        if tag == tagify('road', 'stats'):
            return self.road_stack.value.stats
        elif tag == tagify('lane', 'stats'):
            return self.lane_stack.value.stats
        else:
            log.error('Missing or invalid tag: {0}'.format(tag))
            return None

    def action(self):
        '''
        Iterate over the registered stats requests and fire!
        '''
        while self.stats_req.value:  # stats are msgs with routes
            self._send_stats(
                self.stats_req.value.popleft()
            )


class SaltRaetStatsEventerMaster(SaltRaetStatsEventer):

    def _send_stats(self, msg):
        '''
        Forward a stats message to all subscribed yards
        Stats message has a route
        '''
        y_name = msg['route']['src'][1]
        if y_name not in self.lane_stack.value.nameRemotes:  # subscriber not a remote
            return  # drop msg don't answer

        stats = self._get_stats(msg.get('tag'))
        if stats is None:
            return

        route = {'dst': (None, None, 'event_fire'),
                 'src': (None, self.lane_stack.value.local.name, None)}
        repl = {'route': route, 'tag': msg.get('tag'), 'data': stats}
        self.lane_stack.value.transmit(repl,
                                       self.lane_stack.value.fetchUidByName(y_name))
        self.lane_stack.value.serviceAll()


class SaltRaetStatsEventerMinion(SaltRaetStatsEventer):

    def _send_stats(self, msg):
        '''
        Forward a stats message to all subscribed yards
        Stats message has a route
        '''
        s_estate, s_yard, s_share = msg['route']['src']
        if s_estate not in self.road_stack.value.nameRemotes:  # subscriber not a remote
            return  # drop msg don't answer

        stats = self._get_stats(msg.get('tag'))
        if stats is None:
            return

        route = {'dst': (s_estate, s_yard, 'event_fire'),
                 'src': (self.road_stack.value.name, self.lane_stack.value.name, None)}
        repl = {'route': route, 'tag': msg.get('tag'), 'data': stats}
        self.road_stack.value.transmit(repl,
                                       self.road_stack.value.fetchUidByName(s_estate))
        self.road_stack.value.serviceAll()


class SaltRaetPublisher(ioflo.base.deeding.Deed):
    '''
    Publish to the minions
    FloScript:

    do salt raet publisher

    '''
    Ioinits = {'opts': '.salt.opts',
               'publish': '.salt.var.publish',
               'stack': '.salt.road.manor.stack',
               'availables': '.salt.var.presence.availables',
            }

    def _publish(self, pub_msg):
        '''
        Publish the message out to the targeted minions
        '''
        stack = self.stack.value
        pub_data = pub_msg['return']
        # only publish to available minions by intersecting sets

        minions = (self.availables.value &
                   set((remote.name for remote in list(stack.remotes.values())
                            if remote.kind in [kinds.applKinds.minion,
                                               kinds.applKinds.syndic])))
        for minion in minions:
            uid = self.stack.value.fetchUidByName(minion)
            if uid:
                route = {
                        'dst': (minion, None, 'fun'),
                        'src': (self.stack.value.local.name, None, None)}
                msg = {'route': route, 'pub': pub_data['pub']}
                self.stack.value.message(msg, uid)

    def action(self):
        '''
        Pop the publish queue and publish the requests!
        '''
        while self.publish.value:
            self._publish(
                    self.publish.value.popleft()
                    )


class SaltRaetSetupEngines(ioflo.base.deeding.Deed):
    '''
    Start the engines!
    '''
    Ioinits = {'opts': '.salt.opts',
               'proc_mgr': '.salt.usr.proc_mgr'}

    def action(self):
        '''
        Only call once, this will start the engine processes
        '''
        salt.engines.start_engines(self.opts.value, self.proc_mgr.value)


class SaltRaetSetupBeacon(ioflo.base.deeding.Deed):
    '''
    Create the Beacon subsystem
    '''
    Ioinits = {'opts': '.salt.opts',
               'beacon': '.salt.beacon',
               'modules': '.salt.loader.modules'}

    def action(self):
        '''
        Run the beacons
        '''
        self.beacon.value = salt.beacons.Beacon(
                self.opts.value,
                self.modules.value)


class SaltRaetBeacon(ioflo.base.deeding.Deed):
    '''
    Run the beacons
    '''
    Ioinits = {'opts': '.salt.opts',
               'modules': '.salt.loader.modules',
               'master_events': '.salt.var.master_events',
               'event': '.salt.event.events',
               'beacon': '.salt.beacon'}

    def action(self):
        '''
        Run the beacons
        '''
        if 'config.merge' in self.modules.value:
            b_conf = self.modules.value['config.merge']('beacons')
            if b_conf:
                try:
                    events = self.beacon.value.process(b_conf)
                    self.master_events.value.extend(events)
                    self.event.value.extend(events)
                except Exception:
                    log.error('Error in the beacon system: ', exc_info=True)
        return []


class SaltRaetMasterEvents(ioflo.base.deeding.Deed):
    '''
    Take the events off the master event que and send them to the master to
    be fired
    '''
    Ioinits = {'opts': '.salt.opts',
               'road_stack': '.salt.road.manor.stack',
               'master_events': '.salt.var.master_events'}

    def _prepare(self):
        self.master_events.value = deque()

    def action(self):
        if not self.master_events.value:
            return
        events = []
        for master in self.road_stack.value.remotes:
            master_uid = master
        while self.master_events.value:
            events.append(self.master_events.value.popleft())
        route = {'src': (self.road_stack.value.local.name, None, None),
                 'dst': (next(list(self.road_stack.value.remotes.values())).name, None, 'remote_cmd')}
        load = {'id': self.opts.value['id'],
                'events': events,
                'cmd': '_minion_event'}
        self.road_stack.value.transmit({'route': route, 'load': load},
                                       uid=master_uid)


class SaltRaetSetupMatcher(ioflo.base.deeding.Deed):
    '''
    Make the matcher object
    '''
    Ioinits = {'opts': '.salt.opts',
               'modules': '.salt.loader.modules',
               'matcher': '.salt.matcher'}

    def action(self):
        self.matcher.value = salt.minion.Matcher(
                self.opts.value,
                self.modules.value)
