# -*- coding: utf-8 -*-
'''
Start the reactor!
'''
# pylint: disable=3rd-party-module-not-gated
from __future__ import absolute_import, print_function, unicode_literals
# Import salt libs
import salt.utils.reactor
import salt.utils.event
import salt.utils.stringutils
# Import ioflo libs
import ioflo.base.deeding


@ioflo.base.deeding.deedify(
        salt.utils.stringutils.to_str('SaltRaetReactorFork'),
        ioinits={
            'opts': salt.utils.stringutils.to_str('.salt.opts'),
            'proc_mgr': salt.utils.stringutils.to_str('.salt.usr.proc_mgr')})
def reactor_fork(self):
    '''
    Add a reactor object to the process manager
    '''
    self.proc_mgr.value.add_process(
            salt.utils.reactor.Reactor,
            args=(self.opts.value,))


@ioflo.base.deeding.deedify(
        salt.utils.stringutils.to_str('SaltRaetEventReturnFork'),
        ioinits={
            'opts': salt.utils.stringutils.to_str('.salt.opts'),
            'proc_mgr': salt.utils.stringutils.to_str('.salt.usr.proc_mgr')})
def event_return_fork(self):
    '''
    Add a reactor object to the process manager
    '''
    self.proc_mgr.value.add_process(
            salt.utils.event.EventReturn,
            args=(self.opts.value,))
