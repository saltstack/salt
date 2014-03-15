# -*- coding: utf-8 -*-
'''
The core bahaviuors ued by minion and master
'''
# pylint: disable=W0232

# Import python libs
import multiprocessing

# Import salt libs
import salt.daemons.masterapi
from salt.transport.road.raet import stacking
from salt.transport.road.raet import yarding
from salt.transport.road.raet import raeting

# Import ioflo libs
import ioflo.base.deeding


class WorkerFork(ioflo.base.deeding.Deed):
    '''
    For off the worker procs
    '''
    Ioinits = {'opts': '.salt.opts'}

    def _make_workers(self):
        '''
        Spin up a process for each worker thread
        '''
        for ind in range(int(self.opts['worker_threads'])):
            proc = multiprocessing.Process(
                    target=self._worker, kwargs={'yid': ind + 1}
                    )
            proc.start()

    def _worker(self, yid):
        '''
        Spin up a worker, do this in s multiprocess
        '''
        behaviors = ['salt.transport.road.raet', 'salt.daemons.flo']
        self.preloads.append(('.salt.yid', dict(value=yid)))
        ioflo.app.run.start(
                name='worker{0}'.format(yid),
                period=float(self.opts.value['ioflo_period']),
                stamp=0.0,
                real=self.opts.value['ioflo_realtime'],
                filepath=self.opts.value['worker_floscript'],
                behaviors=behaviors,
                username="",
                password="",
                mode=None,
                houses=None,
                metas=None,
                preloads=self.preloads,
                verbose=int(self.opts.value['ioflo_verbose']),
                )

    def action(self):
        '''
        Run with an enter, starts the worker procs
        '''
        self._make_workers()


class SetupWorker(ioflo.base.deeding.Deed):
    Ioinits = {
            'uxd_stack': '.salt.uxd.stack.stack',
            'opts': '.salt.opts',
            'yid': '.salt.yid',
            'access_keys': '.salt.access_keys',
            }

    def action(self):
        '''
        Set up the uxd stack and behaviors
        '''
        self.uxd_stack.value = stacking.StackUxd(
                lanename=self.opts.value['id'],
                yid=self.yid.value,
                dirpath=self.opts.value['sock_dir'])
        self.uxd_stack.value.Pk = raeting.packKinds.pack
        manor_yard = yarding.Yard(
                yid=0,
                prefix=self.opts.value['id'],
                dirpath=self.opts.value['sock_dir'])
        self.uxd_stack.value.addRemoteYard(manor_yard)
        self.remote = salt.daemons.masterapi.RemoteFuncs(self.opts.value)
        self.local = salt.daemons.masterapi.LocalFuncs(
                self.opts.value,
                self.access_keys.value)
        init = {}
        init['route'] = {
                'src': (None, self.uxd_stack.value.yard.name, None),
                'dst': (None, 'yard0', 'worker_req')
                }
        self.uxd_stack.value.transmit(init, 'yard0')
        self.uxd_stack.value.serviceAll()


class RouterWorker(ioflo.base.deeding.Deed):
    Ioinits = {
            'uxd_stack': '.salt.uxd.stack.stack',
            'opts': '.salt.opts',
            'yid': '.salt.yid',
            'access_keys': '.salt.access_keys',
            }

    def action(self):
        '''
        Read in a command and execute it, send the return back up to the
        main master process
        '''
        self.uxd_stack.value.serviceAll()
        while self.uxd_stack.value.rxMsgs:
            msg = self.uxd_stack.value.rxMsgs.popleft()
            if 'load' in msg:
                cmd = msg['load'].get('cmd')
                if not cmd:
                    continue
                elif cmd.startswith('__'):
                    continue
                ret = {}
                if hasattr(self.remote, cmd):
                    ret['return'] = getattr(self.remote, cmd)(msg['load'])
                elif hasattr(self.local, cmd):
                    ret['return'] = getattr(self.local, cmd)(msg['load'])
                if cmd == 'publish' and 'pub' in ret['return']:
                    r_share = 'pub_ret'
                else:
                    r_share = 'ret'
                ret['route'] = {
                        'src': (self.opts.value['id'], self.yid.value, None),
                        'dst': (msg['route']['src'][0], msg['route']['src'][1], r_share)
                        }
                self.uxd_stack.value.transmit(ret, 'yard0')
                self.uxd_stack.value.serviceAll()
