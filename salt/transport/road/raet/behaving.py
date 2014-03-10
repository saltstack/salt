# -*- coding: utf-8 -*-
'''
behaving.py raet ioflo behaviors

See raeting.py for data format and packet field details.

Layout in DataStore


raet.udp.stack.stack
    value StackUdp
raet.udp.stack.txmsgs
    value deque()
raet.udp.stack.rxmsgs
    value deque()
raet.udp.stack.local
    name host port sigkey prikey
raet.udp.stack.status
    joined allowed idle
raet.udp.stack.destination
    value deid


'''
# pylint: skip-file
# pylint: disable=W0611

import os

# Import Python libs
from collections import deque
try:
    import simplejson as json
except ImportError:
    import json

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base.globaling import *

from ioflo.base import aiding
from ioflo.base import storing
from ioflo.base import deeding

from ioflo.base.consoling import getConsole
console = getConsole()

from . import raeting, packeting, estating, yarding, stacking


class StackUdpRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    StackUdpRaet initialize and run raet udp stack

    '''
    Ioinits = odict(
        inode="raet.udp.stack.",
        stack='stack',
        txmsgs=odict(ipath='txmsgs', ival=deque()),
        rxmsgs=odict(ipath='rxmsgs', ival=deque()),
        local=odict(ipath='local', ival=odict(   name='master',
                                                 dirpath='raet/test/keep',
                                                 main=False,
                                                 auto=True,
                                                 eid=0,
                                                 host='0.0.0.0',
                                                 port=raeting.RAET_PORT,
                                                 sigkey=None,
                                                 prikey=None)),)

    def postinitio(self):
        '''
        Setup stack instance
        '''
        sigkey = self.local.data.sigkey
        prikey = self.local.data.prikey
        name = self.local.data.name
        dirpath = os.path.abspath(os.path.join(self.local.data.dirpath, name))
        auto = self.local.data.auto
        main = self.local.data.main
        ha = (self.local.data.host, self.local.data.port)

        eid = self.local.data.eid
        estate = estating.LocalEstate(  eid=eid,
                                        name=name,
                                        ha=ha,
                                        sigkey=sigkey,
                                        prikey=prikey,)
        txMsgs = self.txmsgs.value
        rxMsgs = self.rxmsgs.value

        self.stack.value = stacking.StackUdp(estate=estate,
                                       store=self.store,
                                       name=name,
                                       auto=auto,
                                       main=main,
                                       dirpath=dirpath,
                                       txMsgs=txMsgs,
                                       rxMsgs=rxMsgs, )

    def action(self, **kwa):
        '''
        Service all the deques for the stack
        '''
        self.stack.value.serviceAll()

class CloserStackUdpRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    CloserStackUdpRaet closes stack server socket connection
    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack', )

    def action(self, **kwa):
        '''
        Close udp socket
        '''
        if self.stack.value and isinstance(self.stack.value, stacking.StackUdp):
            self.stack.value.server.close()

class JoinerStackUdpRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    Initiates join transaction with master
    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack',)

    def action(self, **kwa):
        '''

        '''
        stack = self.stack.value
        if stack and isinstance(stack, stacking.StackUdp):
            stack.join()

class JoinedStackUdpRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    Updates status with .joined of zeroth remote estate (master)
    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack',
        status=odict(ipath='status', ival=odict(joined=False,
                                                allowed=False,
                                                idle=False, )))

    def action(self, **kwa):
        '''
        Update .status share
        '''
        stack = self.stack.value
        joined = False
        if stack and isinstance(stack, stacking.StackUdp):
            if stack.estates:
                joined = stack.estates.values()[0].joined
        self.status.update(joined=joined)

class AllowerStackUdpRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    Initiates allow (CurveCP handshake) transaction with master
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
        if stack and isinstance(stack, stacking.StackUdp):
            stack.allow()
        return None

class AllowedStackUdpRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    Updates status with .allowed of zeroth remote estate (master)
    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack',
        status=odict(ipath='status', ival=odict(joined=False,
                                                allowed=False,
                                                idle=False, )))

    def action(self, **kwa):
        '''
        Update .status share
        '''
        stack = self.stack.value
        allowed = False
        if stack and isinstance(stack, stacking.StackUdp):
            if stack.estates:
                allowed = stack.estates.values()[0].allowed
        self.status.update(allowed=allowed)

class IdledStackUdpRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    Updates idle status to true if there are no oustanding transactions in stack
    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack',
        status=odict(ipath='status', ival=odict(joined=False,
                                                allowed=False,
                                                idle=False, )))

    def action(self, **kwa):
        '''
        Update .status share
        '''
        stack = self.stack.value
        idled = False
        if stack and isinstance(stack, stacking.StackUdp):
            if not stack.transactions:
                idled = True
        self.status.update(idled=idled)

class MessengerStackUdpRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    Puts message on txMsgs deque sent to deid
    Message is composed fields that are parameters to action method
    and is sent to remote estate deid
    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack="stack",
        destination="destination",)

    def action(self, **kwa):
        '''
        Queue up message
        '''
        if kwa:
            msg = odict(kwa)
            stack = self.stack.value
            if stack and isinstance(stack, stacking.StackUdp):
                deid = self.destination.value
                stack.txMsg(msg=msg, deid=deid)


class PrinterStackUdpRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    Prints out messages on rxMsgs queue
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
            msg = rxMsgs.popleft()
            console.terse("\nReceived....\n{0}\n".format(msg))



class StackUxdRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    StackUxdRaet initialize and run raet uxd stack

    '''
    Ioinits = odict(
        inode="raet.uxd.stack.",
        stack='stack',
        txmsgs=odict(ipath='txmsgs', ival=deque()),
        rxmsgs=odict(ipath='rxmsgs', ival=deque()),
        local=odict(ipath='local', ival=odict(name='minion',
                                              yardname="",
                                              lane="maple")),)

    def postinitio(self):
        '''
        Setup stack instance
        '''
        name = self.local.data.name
        yardname = self.local.data.yardname
        lane = self.local.data.lane
        txMsgs = self.txmsgs.value
        rxMsgs = self.rxmsgs.value

        self.stack.value = stacking.StackUxd(
                                       store=self.store,
                                       name=name,
                                       yardname=yardname,
                                       lanename=lane,
                                       txMsgs=txMsgs,
                                       rxMsgs=rxMsgs, )

    def action(self, **kwa):
        '''
        Service all the deques for the stack
        '''
        self.stack.value.serviceAll()

class CloserStackUxdRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    CloserStackUxdRaet closes stack server socket connection
    '''
    Ioinits = odict(
        inode=".raet.uxd.stack.",
        stack='stack',)

    def action(self, **kwa):
        '''
        Close uxd socket
        '''
        if self.stack.value and isinstance(self.stack.value, stacking.StackUxd):
            self.stack.value.server.close()

class AddYardStackUxdRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    AddYardStackUxdRaet closes stack server socket connection
    '''
    Ioinits = odict(
        inode=".raet.uxd.stack.",
        stack='stack',
        yard='yard',
        local=odict(ipath='local', ival=odict(name=None, lane="maple")),)

    def action(self, lane="lane", name=None, **kwa):
        '''
        Adds new yard to stack on lane with yid
        '''
        stack = self.stack.value
        if stack and isinstance(stack, stacking.StackUxd):
            yard = yarding.Yard(stack=stack, prefix=lane, name=name)
            stack.addRemoteYard(yard)
            self.yard.value = yard

class TransmitStackUxdRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    Puts message on txMsgs deque sent to deid
    Message is composed fields that are parameters to action method
    and is sent to remote estate deid
    '''
    Ioinits = odict(
        inode=".raet.uxd.stack.",
        stack="stack",
        dest="dest",)

    def action(self, **kwa):
        '''
        Queue up message
        '''
        if kwa:
            msg = odict(kwa)
            stack = self.stack.value
            if stack and isinstance(stack, stacking.StackUxd):
                name = self.dest.value #destination yard name
                stack.transmit(msg=msg, name=name)


class PrinterStackUxdRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    Prints out messages on rxMsgs queue
    '''
    Ioinits = odict(
        inode=".raet.uxd.stack.",
        stack="stack",
        rxmsgs=odict(ipath='rxmsgs', ival=deque()),)

    def action(self, **kwa):
        '''
        Queue up message
        '''
        rxMsgs = self.rxmsgs.value
        stack = self.stack.value
        while rxMsgs:
            msg = rxMsgs.popleft()
            console.terse("\n{0} Received....\n{1}\n".format(stack.name, msg))
