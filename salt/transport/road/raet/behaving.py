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
    value ddid


'''
# pylint: skip-file
# pylint: disable=W0611

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

from . import raeting, packeting, stacking, devicing


class StackUdpRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    StackUdpRaet initialize and run raet udp stack

    '''
    Ioinits = odict(
        inode="raet.udp.stack.",
        stack='stack',
        txmsgs=odict(ipath='txmsgs', ival=deque()),
        rxmsgs=odict(ipath='rxmsgs', ival=deque()),
        local=odict(ipath='local', ival=odict(   name='minion',
                                                 did=0,
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
        ha = (self.local.data.host, self.local.data.port)
        name = self.local.data.name
        did = self.local.data.did
        device = devicing.LocalDevice(  did=did,
                                        name=name,
                                        ha=ha,
                                        sigkey=sigkey,
                                        prikey=prikey,)
        txMsgs = self.txmsgs.value
        rxMsgs = self.rxmsgs.value

        self.stack.value = stacking.StackUdp(device=device,
                                       store=self.store,
                                       name=name,
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
        Receive any udp packets on server socket and put in rxes
        Send any packets in txes
        '''
        if self.stack.value and isinstance(self.stack.value, stacking.StackUdp):
            self.stack.value.serverUdp.close()

class JoinerStackUdpRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    Initiates join transaction with master
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
            stack.join()

class JoinedStackUdpRaet(deeding.Deed):  # pylint: disable=W0232
    '''
    Updates status with .joined of zeroth remote device (master)
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
            if stack.devices:
                joined = stack.devices.values()[0].joined
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
    Updates status with .allowed of zeroth remote device (master)
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
            if stack.devices:
                allowed = stack.devices.values()[0].allowed
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
    Puts message on txMsgs deque sent to ddid
    Message is composed fields that are parameters to action method
    and is sent to remote device ddid
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
                ddid = self.destination.value
                stack.txMsg(msg=msg, ddid=ddid)


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



