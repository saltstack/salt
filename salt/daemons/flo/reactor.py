# -*- coding: utf-8 -*-
'''
Start the reactor!
'''
# pylint: disable=3rd-party-module-not-gated
from __future__ import absolute_import
# Import salt libs
import salt.utils.reactor
import salt.utils.event
# Import ioflo libs
import ioflo.base.deeding


@ioflo.base.deeding.deedify(
        'SaltRaetReactorFork',
        ioinits={
            'opts': '.salt.opts',
            'proc_mgr': '.salt.usr.proc_mgr'})
def reactor_fork(self):
    '''
    Add a reactor object to the process manager
    '''
    self.proc_mgr.value.add_process(
            salt.utils.reactor.Reactor,
            args=(self.opts.value,))


@ioflo.base.deeding.deedify(
        'SaltRaetEventReturnFork',
        ioinits={
            'opts': '.salt.opts',
            'proc_mgr': '.salt.usr.proc_mgr'})
def event_return_fork(self):
    '''
    Add a reactor object to the process manager
    '''
    self.proc_mgr.value.add_process(
            salt.utils.event.EventReturn,
            args=(self.opts.value,))
