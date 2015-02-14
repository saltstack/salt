# -*- coding: utf-8 -*-
'''
Start the reactor!
'''
# Import salt libs
import salt.utils.reactor
# Import ioflo libs
import ioflo.base.deeding


@ioflo.base.deeding.deedify(
        'SaltRaetReactorFork',
        ioinit={
            'opts': '.salt.opts',
            'proc_mgr': '.salt.usr.proc_mgr'})
def reactor_fork(self):
    '''
    Add a reactor object to the process manager
    '''
    self.proc_mgr.add_process(
            salt.utils.reactor.Reactor,
            args=(self.opts.value,))
