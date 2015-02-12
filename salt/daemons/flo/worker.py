# -*- coding: utf-8 -*-
'''
The core behaviors used by minion and master
'''
# pylint: disable=W0232

from __future__ import absolute_import

# Import python libs
import time
import os
import multiprocessing
import logging
from salt.ext.six.moves import range

# Import salt libs
import salt.daemons.masterapi
from raet import raeting
from raet.lane.stacking import LaneStack
from raet.lane.yarding import RemoteYard

from salt.utils import kinds

# Import ioflo libs
import ioflo.base.deeding

log = logging.getLogger(__name__)

# convert to set once list is larger than about 3 because set hashes
INHIBIT_RETURN = []  # ['_return']  # cmd for which we should not send return


class SaltRaetWorkerFork(ioflo.base.deeding.Deed):
    '''
    Fork off the worker procs
    FloScript:

    do salt raet worker fork at enter

    '''
    Ioinits = {'opts': '.salt.opts',
               'worker_verify': '.salt.var.worker_verify',
               'access_keys': '.salt.access_keys'}

    def _make_workers(self):
        '''
        Spin up a process for each worker thread
        '''
        for index in range(int(self.opts.value['worker_threads'])):
            time.sleep(0.01)
            proc = multiprocessing.Process(
                    target=self._worker, kwargs={'windex': index + 1}
                    )
            proc.start()

    def _worker(self, windex):
        '''
        Spin up a worker, do this in  multiprocess
        windex is worker index
        '''
        self.opts.value['__worker'] = True
        behaviors = ['salt.daemons.flo']
        preloads = [('.salt.opts', dict(value=self.opts.value)),
                    ('.salt.var.worker_verify', dict(value=self.worker_verify.value))]
        preloads.append(('.salt.var.fork.worker.windex', dict(value=windex)))
        preloads.append(
                ('.salt.access_keys', dict(value=self.access_keys.value)))

        console_logdir = self.opts.value.get('ioflo_console_logdir', '')
        if console_logdir:
            consolepath = os.path.join(console_logdir, "worker_{0}.log".format(windex))
        else:  # empty means log to std out
            consolepath = ''

        ioflo.app.run.start(
                name='worker{0}'.format(windex),
                period=float(self.opts.value['ioflo_period']),
                stamp=0.0,
                real=self.opts.value['ioflo_realtime'],
                filepath=self.opts.value['worker_floscript'],
                behaviors=behaviors,
                username='',
                password='',
                mode=None,
                houses=None,
                metas=None,
                preloads=preloads,
                verbose=int(self.opts.value['ioflo_verbose']),
                consolepath=consolepath,
                )

    def action(self):
        '''
        Run with an enter, starts the worker procs
        '''
        self._make_workers()


class SaltRaetWorkerSetup(ioflo.base.deeding.Deed):
    '''
    FloScript:

    do salt raet worker setup at enter

    '''
    Ioinits = {
            'opts': '.salt.opts',
            'windex': '.salt.var.fork.worker.windex',
            'access_keys': '.salt.access_keys',
            'remote_loader': '.salt.loader.remote',
            'local_loader': '.salt.loader.local',
            'inode': '.salt.lane.manor.',
            'stack': 'stack',
            'local': {'ipath': 'local',
                       'ival': {'lanename': 'master'}}
            }

    def action(self):
        '''
        Set up the uxd stack and behaviors
        '''
        name = "worker{0}".format(self.windex.value)
        # master application kind
        kind = self.opts.value['__role']
        if kind not in kinds.APPL_KINDS:
            emsg = ("Invalid application kind = '{0}' for Master Worker.".format(kind))
            log.error(emsg + "\n")
            raise ValueError(emsg)
        if kind in [kinds.APPL_KIND_NAMES[kinds.applKinds.master],
                    kinds.APPL_KIND_NAMES[kinds.applKinds.syndic]]:
            lanename = 'master'
        else:  # workers currently are only supported for masters
            emsg = ("Invalid application kind '{0}' for Master Worker.".format(kind))
            log.error(emsg + '\n')
            raise ValueError(emsg)
        sockdirpath = self.opts.value['sock_dir']
        self.stack.value = LaneStack(
                                     name=name,
                                     lanename=lanename,
                                     sockdirpath=sockdirpath)
        self.stack.value.Pk = raeting.PackKind.pack.value
        manor_yard = RemoteYard(
                                 stack=self.stack.value,
                                 name='manor',
                                 lanename=lanename,
                                 dirpath=sockdirpath)
        self.stack.value.addRemote(manor_yard)
        self.remote_loader.value = salt.daemons.masterapi.RemoteFuncs(
                                                        self.opts.value)
        self.local_loader.value = salt.daemons.masterapi.LocalFuncs(
                                                        self.opts.value,
                                                        self.access_keys.value)
        init = {}
        init['route'] = {
                'src': (None, self.stack.value.local.name, None),
                'dst': (None, manor_yard.name, 'worker_req')
                }
        self.stack.value.transmit(init, self.stack.value.fetchUidByName(manor_yard.name))
        self.stack.value.serviceAll()

    def __del__(self):
        self.stack.server.close()


class SaltRaetWorkerRouter(ioflo.base.deeding.Deed):
    '''
    FloScript:

    do salt raet worker router

    '''
    Ioinits = {
            'lane_stack': '.salt.lane.manor.stack',
            'road_stack': '.salt.road.manor.stack',
            'opts': '.salt.opts',
            'worker_verify': '.salt.var.worker_verify',
            'remote_loader': '.salt.loader.remote',
            'local_loader': '.salt.loader.local',
            }

    def action(self):
        '''
        Read in a command and execute it, send the return back up to the
        main master process
        '''
        self.lane_stack.value.serviceAll()
        while self.lane_stack.value.rxMsgs:
            msg, sender = self.lane_stack.value.rxMsgs.popleft()
            try:
                s_estate, s_yard, s_share = msg['route']['src']
                d_estate, d_yard, d_share = msg['route']['dst']
            except (ValueError, IndexError):
                log.error('Received invalid message: {0}'.format(msg))
                return

            log.debug("**** Worker Router rxMsg\n   msg= {0}\n".format(msg))

            if 'load' in msg:
                cmd = msg['load'].get('cmd')
                if not cmd:
                    continue
                elif cmd.startswith('__'):
                    continue
                ret = {}
                if d_share == 'remote_cmd':
                    if hasattr(self.remote_loader.value, cmd):
                        ret['return'] = getattr(self.remote_loader.value, cmd)(msg['load'])
                elif d_share == 'local_cmd':
                    if hasattr(self.local_loader.value, cmd):
                        ret['return'] = getattr(self.local_loader.value, cmd)(msg['load'])
                else:
                    ret = {'error': 'Invalid request'}
                if cmd == 'publish' and 'pub' in ret.get('return', {}):
                    r_share = 'pub_ret'
                    ret['__worker_verify'] = self.worker_verify.value
                else:
                    r_share = s_share
                if cmd not in INHIBIT_RETURN:
                    ret['route'] = {
                            'src': (None, self.lane_stack.value.local.name, None),
                            'dst': (s_estate, s_yard, r_share)
                            }
                    self.lane_stack.value.transmit(ret,
                            self.lane_stack.value.fetchUidByName('manor'))
                    self.lane_stack.value.serviceAll()
