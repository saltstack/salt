# -*- coding: utf-8 -*-
'''
The core bahaviuors ued by minion and master
'''
# pylint: disable=W0232

# Import python libs
import multiprocessing

# Import salt libs
import salt.daemons.masterapi
from raet import raeting
from raet.lane.stacking import LaneStack
from raet.lane.yarding import RemoteYard


# Import ioflo libs
import ioflo.base.deeding


class WorkerFork(ioflo.base.deeding.Deed):
    '''
    Fork off the worker procs
    FloScript:

    do worker fork at enter

    '''
    Ioinits = {'opts': '.salt.opts',
               'access_keys': '.salt.access_keys'}

    def _make_workers(self):
        '''
        Spin up a process for each worker thread
        '''
        for ind in range(int(self.opts.value['worker_threads'])):
            proc = multiprocessing.Process(
                    target=self._worker, kwargs={'yid': ind + 1}
                    )
            proc.start()

    def _worker(self, yid):
        '''
        Spin up a worker, do this in s multiprocess
        '''
        self.opts.value['__worker'] = True
        behaviors = ['salt.daemons.flo']
        preloads = [('.salt.opts', dict(value=self.opts.value))]
        preloads.append(('.salt.yid', dict(value=yid)))
        preloads.append(
                ('.salt.access_keys', dict(value=self.access_keys.value)))
        ioflo.app.run.start(
                name='worker{0}'.format(yid),
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
                )

    def action(self):
        '''
        Run with an enter, starts the worker procs
        '''
        self._make_workers()


class WorkerSetup(ioflo.base.deeding.Deed):
    '''
    FloScript:

    do worker setup at enter

    '''
    Ioinits = {
            'uxd_stack': '.salt.uxd.stack.stack',
            'opts': '.salt.opts',
            'yid': '.salt.yid',
            'access_keys': '.salt.access_keys',
            'remote': '.salt.loader.remote',
            'local': '.salt.loader.local',
            }

    def action(self):
        '''
        Set up the uxd stack and behaviors
        '''
        #import wingdbstub
        self.uxd_stack.value = LaneStack(
                lanename=self.opts.value.get('id', 'master'),
                yid=self.yid.value,
                sockdirpath=self.opts.value['sock_dir'])
        self.uxd_stack.value.Pk = raeting.packKinds.pack
        manor_yard = RemoteYard(
                yid=0,
                lanename=self.opts.value.get('id', 'master'),
                dirpath=self.opts.value['sock_dir'])
        self.uxd_stack.value.addRemote(manor_yard)
        self.remote.value = salt.daemons.masterapi.RemoteFuncs(self.opts.value)
        self.local.value = salt.daemons.masterapi.LocalFuncs(
                self.opts.value,
                self.access_keys.value)
        init = {}
        init['route'] = {
                'src': (None, self.uxd_stack.value.local.name, None),
                'dst': (None, 'yard0', 'worker_req')
                }
        self.uxd_stack.value.transmit(init, self.uxd_stack.value.uids.get('yard0'))
        self.uxd_stack.value.serviceAll()


class WorkerRouter(ioflo.base.deeding.Deed):
    '''
    FloScript:

    do worker router

    '''
    Ioinits = {
            'uxd_stack': '.salt.uxd.stack.stack',
            'opts': '.salt.opts',
            'yid': '.salt.yid',
            'remote': '.salt.loader.remote',
            'local': '.salt.loader.local',
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
                if hasattr(self.remote.value, cmd):
                    ret['return'] = getattr(self.remote.value, cmd)(msg['load'])
                elif hasattr(self.local.value, cmd):
                    ret['return'] = getattr(self.local.value, cmd)(msg['load'])
                if cmd == 'publish' and 'pub' in ret['return']:
                    r_share = 'pub_ret'
                else:
                    r_share = 'ret'
                ret['route'] = {
                        'src': (self.opts.value.get('id', 'master'), self.uxd_stack.value.local.name, None),
                        'dst': (msg['route']['src'][0], msg['route']['src'][1], r_share)
                        }
                self.uxd_stack.value.transmit(ret, self.uxd_stack.value.uids.get('yard0'))
                self.uxd_stack.value.serviceAll()
