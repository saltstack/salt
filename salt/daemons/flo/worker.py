# -*- coding: utf-8 -*-
'''
The core bahaviuors ued by minion and master
'''
# pylint: disable=W0232

# Import salt libs
import salt.daemons.masterapi
from salt.transport.road.raet import stacking
from salt.transport.road.raet import yarding

# Import ioflo libs
import ioflo.base.deeding


class RouterWorker(ioflo.base.deeding.Deed):
    Ioinits = {
            'uxd_stack': '.salt.uxd.stack.stack',
            'opts': '.salt.opts',
            'yid': '.salt.yid'
            }

    def postioinit(self):
        '''
        Set up the uxd stack
        '''
        self.uxd_stack.value = stacking.StackUxd(
                lanename=self.opts.value['id'],
                yid=self.yid.value,
                dirpath=self.opts.value['sock_dir'])
        manor_yard = yarding.Yard(
                yid=0,
                prefix=self.opts.value['id'],
                dirpath=self.opts.value['sock_dir'])
        self.uxd_stack.value.addRemoteYard(manor_yard)
        self.remote = salt.daemons.masterapi.RemoteFuncs(self.opts.value)
        self.local = salt.daemons.masterapi.LocalFuncs(self.opts.value)

    def action(self):
        '''
        Read in a command and execute it, send the return back up to the
        main master process
        '''
        self.uxd_stack.value.serviceAll()
        while self.uxd_stack.value.rxMsgs:
            msg = self.uxd_stack.value.rxMsgs.popleft()
            if 'load' in msg:
                cmd = msg['load'].get['cmd']
                if not cmd:
                    continue
                elif cmd.startswith('__'):
                    continue
                ret = {}
                if hasattr(self.remote, cmd):
                    ret['return'] = getattr(self.remote, cmd)(msg['load'])
                elif hasattr(self.local, cmd):
                    ret['return'] = getattr(self.local, cmd)(msg['load'])
                ret['route'] = {
                        'src': (self.opts.value['id'], self.yid.value, None),
                        'dst': (msg['route']['src'][0], msg['route']['src'][1], 'ret')
                        }
                self.uxd_stack.value.transmit(ret, 'yard0')
                self.uxd_stack.value.serviceAll()
