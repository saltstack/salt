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
        rxmsgs=odict(ipath='rxmsgs', ival=deque(), iown=True),
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
        self.stack = stacking.StackUdp(device=device)

    def action(self, **kwa):
        '''
        Service all the deques for the stack
        '''
        self.stack.serviceAll()

class CloserStackUdpRaet(deeding.ParamDeed):  # pylint: disable=W0232
    '''
    CloserStackUdpRaet closes stack server socket connection
    '''
    Ioinits = odict(
        inode="raet.udp.stack.",
        stack='stack', )

    def action(self, stack, **kwa):
        '''
        Receive any udp packets on server socket and put in rxes
        Send any packets in txes
        '''
        if stack.value:
            if isinstance(stack.value, stacking.StackUdp):
                stack.value.serverUdp.close()
        return None


class TransmitterRaet(deeding.ParamDeed):  # pylint: disable=W0232
    '''
    TransmitterRaet pushes packed packet in onto txes transmit deque and assigns
    destination ha from meta data

    inherited attributes
        .name is actor name string
        .store is data store ref
        .ioinits is dict of io init data for initio
        ._parametric is flag for initio to not create attributes
    '''
    Ioinits = odict(
        data='data',
        txes=odict(ipath='.raet.media.txes', ival=deque()),)

    def action(self, data, txes, **kwa):
        '''
        Transmission action
        '''
        if data.value:
            da = (data.value['meta']['dh'], data.value['meta']['dp'])
            txes.value.append((data.value['pack'], da))
        return None


class ReceiverRaet(deeding.ParamDeed):  # pylint: disable=W0232
    '''
    ReceiverRaet pulls packet from rxes deque and puts into new data
    and assigns meta data source ha using received ha

    inherited attributes
        .name is actor name string
        .store is data store ref
        .ioinits is dict of io init data for initio
        ._parametric is flag for initio to not create attributes
    '''
    Ioinits = odict(
            data='data',
            rxes=odict(ipath='.raet.media.rxes', ival=deque()), )

    def action(self, data, rxes, **kwa):
        '''
        Handle recived packet
        '''
        if rxes.value:
            rx, sa, da = rxes.value.popleft()
            data.value = raeting.defaultData()
            data.value['pack'] = rx
            data.value['meta']['sh'], data.value['meta']['sp'] = sa
            data.value['meta']['dh'], data.value['meta']['dp'] = da
        return None

