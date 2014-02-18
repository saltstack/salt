# -*- coding: utf-8 -*-
'''
stacking.py raet protocol stacking classes
'''
# pylint: skip-file
# pylint: disable=W0611

# Import python libs
import socket
from collections import deque

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base import aiding

from . import raeting
from . import nacling
from . import packeting
from . import devicing
from . import transacting

from ioflo.base.consoling import getConsole
console = getConsole()

class StackUdp(object):
    '''
    RAET protocol UDP stack object
    '''
    Count = 0
    Hk = raeting.headKinds.json # stack default
    Bk = raeting.bodyKinds.json # stack default

    def __init__(self,
                 name='',
                 version=raeting.VERSION,
                 device=None,
                 did=None,
                 ha=("", raeting.RAET_PORT)):
        '''
        Setup StackUdp instance
        '''
        if not name:
            name = "stack{0}".format(StackUdp.Count)
            StackUdp.Count += 1
        self.name = name
        self.version = version
        self.devices = odict() # remote devices attached to this stack
         # local device for this stack
        self.device = device or devicing.LocalDevice(stack=self, did=did, ha=ha)
        self.transactions = odict() #transactions
        self.udpRxes = deque()
        self.udpTxes = deque()
        self.serverUdp = aiding.SocketUdpNb(ha=self.device.ha)
        self.serverUdp.reopen()  # open socket
        self.device.ha = self.serverUdp.ha  # update device host address after open

    def addRemoteDevice(self, device, did=None):
        '''
        Add a remote device to .devices
        '''
        if did is None:
            did = device.did

        if did in self.devices:
            msg = "Device with id '{0}' alreadys exists".format(did)
            raise raeting.StackError(msg)
        device.stack = self
        self.devices[did] = device

    def moveRemoteDevice(self, odid, ndid):
        '''
        Move device at odid to ndid
        '''
        if ndid in self.devices:
            msg = "Cannot move, '{0}' already exists".format(ndid)
            raise raeting.StackError(msg)

        if odid not in self.devices:
            msg = "Cannot move '{0}' does not exist".format(odid)
            raise raeting.StackError(msg)

        device = self.devices[odid]
        del self.devices[odid]
        device.did = ndid
        self.devices.insert(0, device.did, device)

    def addTransaction(self, index, transaction):
        '''
        Safely add transaction at index If not already there
        '''
        self.transactions[index] = transaction
        print "Added {0} transaction to {1} at '{2}'".format(
                transaction.__class__.__name__, self.name, index)

    def removeTransaction(self, index, transaction=None):
        '''
        Safely remove transaction at index If transaction identity same
        If transaction is None then remove without comparing identity
        '''
        if index in self.transactions:
            if transaction:
                if transaction is self.transactions[index]:
                    del  self.transactions[index]
            else:
                del self.transactions[index]


    def serviceUdp(self):
        '''
        Service the UDP receive and transmit queues
        '''
        if self.serverUdp:
            while True:
                rx, ra = self.serverUdp.receive()  # if no data the duple is ('',None)
                if not rx:  # no received data so break
                    break
                # triple = ( packet, source address, destination address)
                self.udpRxes.append((rx, ra, self.serverUdp.ha))

            while self.udpTxes:
                tx, ta = self.udpTxes.popleft()  # duple = (packet, destination address)
                self.serverUdp.send(tx, ta)

        return None

    def txUdp(self, packed, ddid):
        '''
        Queue duple of (packed, da) on stack transmit queue
        Where da is the ip destination (host,port) address associated with
        the device with ddid
        '''
        if ddid not in self.devices:
            msg = "Invalid destination device id '{0}'".format(ddid)
            raise raeting.StackError(msg)
        self.udpTxes.append((packed, self.devices[ddid].ha))

    def fetchParseUdpRx(self):
        '''
        Fetch from UDP deque next packet tuple
        Parse packet
        Return packet if verified and destination did matches
        Otherwise return None
        '''
        try:
            raw, ra, da = self.udpRxes.popleft()
        except IndexError:
            return None

        print "{0} received\n{1}".format(self.name, raw)

        packet = packeting.RxPacket(stack=self, packed=raw)
        try:
            packet.parseOuter()
        except raeting.PacketError as ex:
            print ex
            return None

        ddid = packet.data['dd']
        if ddid != 0 and self.device.did != 0 and ddid != self.device.did:
            emsg = "Invalid destination did = {0}. Dropping packet.".format(ddid)
            print emsg
            return None

        sh, sp = ra
        dh, dp = da
        packet.data.update(sh=sh, sp=sp, dh=dh, dp=dp)

        try:
            packet.parseInner()
        except raeting.PacketError as ex:
            print ex
            return None

        return packet

    def processUdpRx(self):
        '''
        Retrieve next packet from stack receive queue if any and parse
        Process associated transaction or reply with new correspondent transaction
        '''
        packet = self.fetchParseUdpRx()
        if not packet:
            return

        print "{0} received\n{1}".format(self.name, packet.data)
        print "{0} received\n{1}".format(self.name, packet.body.data)
        print "{0} received packet index = '{1}'".format(self.name, packet.index)

        trans = self.transactions.get(packet.index, None)
        if trans:
            trans.receive(packet)
            return

        if packet.data['cf']: #correspondent to stale transaction so drop
            print "{0} Stale Transaction, dropping ...".format(self.name)
            # Should send abort nack to drop transaction on other side
            return

        self.reply(packet)

    def reply(self, packet):
        '''
        Reply to packet with corresponding transaction or action
        '''
        if (packet.data['tk'] == raeting.trnsKinds.join and
                packet.data['pk'] == raeting.pcktKinds.request and
                packet.data['si'] == 0):
            self.replyJoin(packet)

        if (packet.data['tk'] == raeting.trnsKinds.allow and
                packet.data['pk'] == raeting.pcktKinds.hello and
                packet.data['si'] != 0):
            self.replyEndow(packet)

    def join(self):
        '''
        Initiate join transaction
        '''
        data = odict(hk=self.Hk, bk=self.Bk)
        joiner = transacting.Joiner(stack=self, txData=data)
        joiner.join()

    def replyJoin(self, packet):
        '''
        Correspond to new join transaction
        '''
        data = odict(hk=self.Hk, bk=self.Bk)
        joinent = transacting.Joinent(stack=self,
                                        sid=packet.data['si'],
                                        tid=packet.data['ti'],
                                        txData=data,
                                        rxPacket=packet)
        joinent.join() #assigns .rdid here
        # need to perform the check for accepted status somewhere
        joinent.accept()

    def endow(self, rdid=None):
        '''
        Initiate endow transaction
        '''
        data = odict(hk=self.Hk, bk=raeting.bodyKinds.raw)
        endower = transacting.Allower(stack=self, rdid=rdid, txData=data)
        endower.hello()

    def replyEndow(self, packet):
        '''
        Correspond to new endow transaction
        '''
        data = odict(hk=self.Hk, bk=raeting.bodyKinds.raw)
        endowent = transacting.Allowent(stack=self,
                                        rdid=packet.data['sd'],
                                        sid=packet.data['si'],
                                        tid=packet.data['ti'],
                                        txData=data,
                                        rxPacket=packet)
        endowent.hello()

