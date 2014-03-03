# -*- coding: utf-8 -*-
'''
stacking.py raet protocol stacking classes
'''
# pylint: skip-file
# pylint: disable=W0611

# Import python libs
import socket
import os
from collections import deque,  Mapping
try:
    import simplejson as json
except ImportError:
    import json

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base import aiding
from ioflo.base import storing

from . import raeting
from . import nacling
from . import packeting
from . import devicing
from . import yarding
from . import keeping
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
    Fk = raeting.footKinds.nacl # stack default
    Ck = raeting.coatKinds.nacl # stack default

    def __init__(self,
                 name='',
                 version=raeting.VERSION,
                 store=None,
                 device=None,
                 did=None,
                 ha=("", raeting.RAET_PORT),
                 rxMsgs = None,
                 txMsgs = None,
                 udpRxes = None,
                 udpTxes = None,
                 road = None,
                 safe = None,
                 ):
        '''
        Setup StackUdp instance
        '''
        if not name:
            name = "stackUdp{0}".format(StackUdp.Count)
            StackUdp.Count += 1
        self.name = name
        self.version = version
        self.store = store or storing.Store(stamp=0.0)
        self.devices = odict() # remote devices attached to this stack by did
        self.dids = odict() # reverse lookup did by device.name
         # local device for this stack
        self.device = device or devicing.LocalDevice(stack=self, did=did, ha=ha)
        self.transactions = odict() #transactions
        self.rxMsgs = rxMsgs if rxMsgs is not None else deque() # messages received
        self.txMsgs = txMsgs if txMsgs is not None else deque() # messages to transmit
        #(msg, ddid) ddid=0 is broadcast
        self.udpRxes = udpRxes if udpRxes is not None else deque() # udp packets received
        self.udpTxes = udpTxes if udpTxes is not None else deque() # udp packet to transmit
        self.road = road or keeping.RoadKeep()
        self.safe = safe or keeping.SafeKeep()
        self.serverUdp = aiding.SocketUdpNb(ha=self.device.ha, bufsize=raeting.MAX_MESSAGE_SIZE)
        self.serverUdp.reopen()  # open socket
        self.device.ha = self.serverUdp.ha  # update device host address after open

        #self.road.dumpLocalDevice(self.device)
        #self.safe.dumpLocalDevice(self.device)

    def fetchRemoteDeviceByHostPort(self, host, port):
        '''
        Search for remote device with matching (host, port)
        Return device if found Otherwise return None
        '''
        for device in self.devices.values():
            if device.host == host and device.port == port:
                return device

        return None

    def fetchRemoteDeviceByName(self, name):
        '''
        Search for remote device with matching name
        Return device if found Otherwise return None
        '''
        return self.devices.get(self.dids.get(name))

    def addRemoteDevice(self, device, did=None):
        '''
        Add a remote device to .devices
        '''
        if did is None:
            did = device.did

        if did in self.devices:
            emsg = "Device with id '{0}' alreadys exists".format(did)
            raise raeting.StackError(emsg)
        device.stack = self
        self.devices[did] = device
        if device.name in self.dids:
            emsg = "Device with name '{0}' alreadys exists".format(device.name)
            raise raeting.StackError(emsg)
        self.dids[device.name] = device.did

    def moveRemoteDevice(self, old, new):
        '''
        Move device at key old did to key new did but keep same index
        '''
        if new in self.devices:
            emsg = "Cannot move, '{0}' already exists".format(new)
            raise raeting.StackError(emsg)

        if old not in self.devices:
            emsg = "Cannot move '{0}' does not exist".format(old)
            raise raeting.StackError(emsg)

        device = self.devices[old]
        index = self.devices.keys().index(old)
        device.did = new
        self.dids[device.name] = new
        del self.devices[old]
        self.devices.insert(index, device.did, device)

    def renameRemoteDevice(self, old, new):
        '''
        rename device with old name to new name but keep same index
        '''
        if new in self.dids:
            emsg = "Cannot rename, '{0}' already exists".format(new)
            raise raeting.StackError(emsg)

        if old not in self.dids:
            emsg = "Cannot rename '{0}' does not exist".format(old)
            raise raeting.StackError(emsg)

        did = self.dids[old]
        device = self.devices[did]
        device.name = new
        index = self.dids.keys().index(old)
        del self.dids[old]
        self.dids.insert(index, device.name, device.did)

    def removeRemoteDevice(self, did):
        '''
        Remove device at key did
        '''
        if did not in self.devices:
            emsg = "Cannot remove, '{0}' does not exist".format(did)
            raise raeting.StackError(emsg)

        device = self.devices[did]
        del self.devices[did]
        del self.dids[device.name]

    def addTransaction(self, index, transaction):
        '''
        Safely add transaction at index If not already there
        '''
        self.transactions[index] = transaction
        console.verbose( "Added {0} transaction to {1} at '{2}'\n".format(
                transaction.__class__.__name__, self.name, index))

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

    def serviceAll(self):
        '''
        Service or Process:
           UDP Socket receive
           UdpRxes queue
           process
           txMsgs queue
           udpTxes queue
           UDP Socket send

        '''
        if self.serverUdp:
            while True:
                rx, ra = self.serverUdp.receive()  # if no data the duple is ('',None)
                if not rx:  # no received data so break
                    break
                # triple = ( packet, source address, destination address)
                self.udpRxes.append((rx, ra, self.serverUdp.ha))

            self.serviceUdpRx()

            self.process()

            self.serviceTxMsg()

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

    def txMsg(self, msg, ddid=None):
        '''
        Append duple (msg,ddid) to .txMsgs deque
        If msg is not mapping then raises exception
        If ddid is None then it will default to the first entry in .devices
        '''
        if not isinstance(msg, Mapping):
            emsg = "Invalid msg, not a mapping {0}".format(msg)
            raise raeting.StackError(emsg)
        self.txMsgs.append((msg, ddid))

    def serviceTxMsg(self):
        '''
        Service .udpTxMsgs queue of outgoint udp messages for message transactions
        '''
        while self.txMsgs:
            body, ddid = self.txMsgs.popleft() # duple (body dict, destination did)
            self.message(body, ddid)
            console.verbose("{0} sending\n{1}\n".format(self.name, body))

    def fetchParseUdpRx(self):
        '''
        Fetch from UDP deque next packet tuple
        Parse packet
        Return packet if verified and destination did matches
        Otherwise return None
        '''
        try:
            raw, sa, da = self.udpRxes.popleft()
        except IndexError:
            return None

        console.verbose("{0} received packet\n{1}\n".format(self.name, raw))

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

        sh, sp = sa
        dh, dp = da
        packet.data.update(sh=sh, sp=sp, dh=dh, dp=dp)

        return packet # outer only has been parsed

    def processUdpRx(self):
        '''
        Retrieve next packet from stack receive queue if any and parse
        Process associated transaction or reply with new correspondent transaction
        '''
        packet = self.fetchParseUdpRx()
        if not packet:
            return

        console.verbose("{0} received packet data\n{1}\n".format(self.name, packet.data))
        console.verbose("{0} received packet index = '{1}'\n".format(self.name, packet.index))

        trans = self.transactions.get(packet.index, None)
        if trans:
            trans.receive(packet)
            return

        if packet.data['cf']: #correspondent to stale transaction so drop
            print "{0} Stale Transaction, dropping ...".format(self.name)
            # Should send abort nack to drop transaction on other side
            return

        self.reply(packet)

    def serviceUdpRx(self):
        '''
        Process all packets in .udpRxes deque
        '''
        while self.udpRxes:
            self.processUdpRx()

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
            self.replyAllow(packet)

        if (packet.data['tk'] == raeting.trnsKinds.message and
                packet.data['pk'] == raeting.pcktKinds.message and
                packet.data['si'] != 0):
            self.replyMessage(packet)

    def process(self):
        '''
        Call .process or all transactions to allow timer based processing
        '''
        for transaction in self.transactions.values():
            transaction.process()

    def parseInner(self, packet):
        '''
        Parse inner of packet and return
        Assume all drop checks done
        '''
        try:
            packet.parseInner()
            console.verbose("{0} received packet body\n{1}\n".format(self.name, packet.body.data))
        except raeting.PacketError as ex:
            print ex
            return None
        return packet

    def join(self, mha=None):
        '''
        Initiate join transaction
        '''
        data = odict(hk=self.Hk, bk=self.Bk)
        joiner = transacting.Joiner(stack=self, txData=data, mha=mha)
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
        #joinent.accept() now in joinent.process()

    def allow(self, rdid=None):
        '''
        Initiate allow transaction
        '''
        data = odict(hk=self.Hk, bk=raeting.bodyKinds.raw, fk=self.Fk)
        allower = transacting.Allower(stack=self, rdid=rdid, txData=data)
        allower.hello()

    def replyAllow(self, packet):
        '''
        Correspond to new allow transaction
        '''
        data = odict(hk=self.Hk, bk=raeting.bodyKinds.raw, fk=self.Fk)
        allowent = transacting.Allowent(stack=self,
                                        rdid=packet.data['sd'],
                                        sid=packet.data['si'],
                                        tid=packet.data['ti'],
                                        txData=data,
                                        rxPacket=packet)
        allowent.hello()

    def message(self, body=None, ddid=None):
        '''
        Initiate message transaction
        '''
        data = odict(hk=self.Hk, bk=self.Bk, fk=self.Fk, ck=self.Ck)
        messenger = transacting.Messenger(stack=self, txData=data, rdid=ddid)
        messenger.message(body)

    def replyMessage(self, packet):
        '''
        Correspond to new Message transaction
        '''
        data = odict(hk=self.Hk, bk=self.Bk, fk=self.Fk, ck=self.Ck)
        messengent = transacting.Messengent(stack=self,
                                        rdid=packet.data['sd'],
                                        sid=packet.data['si'],
                                        tid=packet.data['ti'],
                                        txData=data,
                                        rxPacket=packet)
        messengent.message()


class StackUxd(object):
    '''
    RAET protocol UXD (unix domain) socket stack object
    '''
    Count = 0
    PackKind = raeting.bodyKinds.json
    Accept = True # accept any uxd messages if True from yards not already in lanes

    def __init__(self,
                 name='',
                 version=raeting.VERSION,
                 store=None,
                 lanename='lane',
                 yard=None,
                 yid=None,
                 yardname='',
                 ha='',
                 rxMsgs = None,
                 txMsgs = None,
                 uxdRxes = None,
                 uxdTxes = None,
                 lane=None,
                 accept=None,
                 dirpath=None,
                 ):
        '''
        Setup StackUxd instance
        '''
        if not name:
            name = "stackUxd{0}".format(StackUxd.Count)
            StackUxd.Count += 1
        self.name = name
        self.version = version
        self.store = store or storing.Store(stamp=0.0)
        self.yards = odict() # remote uxd yards attached to this stack by name
        self.names = odict() # remote uxd yard names  by ha
        self.yard = yard or yarding.Yard(stack=self,
                                         name=yardname,
                                         yid=yid,
                                         ha=ha,
                                         prefix=lanename,
                                         dirpath=dirpath)
        self.rxMsgs = rxMsgs if rxMsgs is not None else deque() # messages received
        self.txMsgs = txMsgs if txMsgs is not None else deque() # messages to transmit
        self.uxdRxes = uxdRxes if uxdRxes is not None else deque() # uxd packets received
        self.uxdTxes = uxdTxes if uxdTxes is not None else deque() # uxd packets to transmit
        self.lane = lane # or keeping.LaneKeep()
        self.accept = self.Accept if accept is None else accept #accept uxd msg if not in lane
        self.serverUxd = aiding.SocketUxdNb(ha=self.yard.ha, bufsize=raeting.MAX_MESSAGE_SIZE)
        self.serverUxd.reopen()  # open socket
        self.yard.ha = self.serverUxd.ha  # update device host address after open

        #self.lane.dumpLocalLane(self.yard)

    def fetchRemoteYardByHa(self, ha):
        '''
        Search for remote yard with matching ha
        Return yard if found Otherwise return None
        '''
        return self.yards.get(self.names.get(ha))

    def addRemoteYard(self, yard, name=None):
        '''
        Add a remote yard to .yards
        '''
        if name is None:
            name = yard.name

        if name in self.yards or name == self.yard.name:
            emsg = "Device with name '{0}' alreadys exists".format(name)
            raise raeting.StackError(emsg)
        yard.stack = self
        self.yards[name] = yard
        if yard.ha in self.names or yard.ha == self.yard.ha:
            emsg = "Yard with ha '{0}' alreadys exists".format(yard.ha)
            raise raeting.StackError(emsg)
        self.names[yard.ha] = yard.name

    def moveRemoteYard(self, old, new):
        '''
        Move yard at key old name to key new name but keep same index
        '''
        if new in self.yards:
            emsg = "Cannot move, '{0}' already exists".format(new)
            raise raeting.StackError(emsg)

        if old not in self.yards:
            emsg = "Cannot move '{0}' does not exist".format(old)
            raise raeting.StackError(emsg)

        yard = self.yards[old]
        index = self.yards.keys().index(old)
        yard.name = new
        self.names[yard.ha] = new
        del self.yards[old]
        self.yards.insert(index, yard.name, yard)

    def rehaRemoteYard(self, old, new):
        '''
        change device with old ha to new ha but keep same index
        '''
        if new in self.names:
            emsg = "Cannot reha, '{0}' already exists".format(new)
            raise raeting.StackError(emsg)

        if old not in self.names:
            emsg = "Cannot reha '{0}' does not exist".format(old)
            raise raeting.StackError(emsg)

        name = self.names[old]
        yard = self.yards[name]
        yard.ha = new
        index = self.names.keys().index(old)
        del self.names[old]
        self.yards.insert(index, yard.ha, yard.name)

    def removeRemoteYard(self, name):
        '''
        Remove yard at key name
        '''
        if name not in self.yards:
            emsg = "Cannot remove, '{0}' does not exist".format(name)
            raise raeting.StackError(emsg)

        yard = self.yards[name]
        del self.yards[name]
        del self.names[yard.ha]

    def serviceUxd(self):
        '''
        Service the UXD receive and transmit queues
        '''
        if self.serverUxd:
            while True:
                rx, ra = self.serverUxd.receive()  # if no data the duple is ('',None)
                if not rx:  # no received data so break
                    break
                # triple = ( packet, source address, destination address)
                self.uxdRxes.append((rx, ra, self.serverUxd.ha))

            while self.uxdTxes:
                tx, ta = self.uxdTxes.popleft()  # duple = (packet, destination address)
                self.serverUxd.send(tx, ta)

        return None

    def serviceAll(self):
        '''
        Service or Process:
           Uxd Socket receive
           uxdRxes queue
           txMsgs queue
           uxdTxes queue
           Uxd Socket send

        '''
        if self.serverUxd:
            while True:
                rx, ra = self.serverUxd.receive()  # if no data the duple is ('',None)
                if not rx:  # no received data so break
                    break
                # triple = ( packet, source address, destination address)
                self.uxdRxes.append((rx, ra, self.serverUxd.ha))

            self.serviceUxdRx()

            self.serviceTxMsg()

            while self.uxdTxes:
                tx, ta = self.uxdTxes.popleft()  # duple = (packet, destination address)
                self.serverUxd.send(tx, ta)

        return None

    def txUxd(self, packed, name):
        '''
        Queue duple of (packed, da) on stack transmit queue
        Where da is the ip destination address associated with
        the device with name
        If name is None then it will default to the first entry in .yards
        '''
        if name is None:
            if not self.yards:
                emsg = "No yard to send to"
                raise raeting.StackError(emsg)
            name = self.yards.values()[0].name
        if name not in self.yards:
            msg = "Invalid destination yard name '{0}'".format(name)
            raise raeting.StackError(msg)
        self.uxdTxes.append((packed, self.yards[name].ha))

    def txMsg(self, msg, name=None):
        '''
        Append duple (msg, name) to .txMsgs deque
        If msg is not mapping then raises exception
        If name is None then txUxd will supply default
        '''
        if not isinstance(msg, Mapping):
            emsg = "Invalid msg, not a mapping {0}".format(msg)
            raise raeting.StackError(emsg)
        self.txMsgs.append((msg, name))

    transmit = txMsg # alias

    def packUxdTx(self, body=None, name=None, kind=None):
        '''
        Pack serialize message body data
        '''
        if kind is None:
            kind = self.PackKind

        packed = ""
        if kind not in [raeting.bodyKinds.json]:
            emsg = "Invalid body pack kind '{0}'".format(kind)
            raise raeting.StackError(emsg)

        if kind == raeting.bodyKinds.json:
            head = 'RAET\njson\n\n'
            packed = "".join([head, json.dumps(body, separators=(',', ':'))])

        if len(packed) > raeting.MAX_MESSAGE_SIZE:
            emsg = "Message length of {0}, exceeds max of {1}".format(
                     len(packed), raeting.MAX_MESSAGE_SIZE)
            raise raeting.StackError(emsg)

        return packed

    def serviceTxMsg(self):
        '''
        Service .txMsgs queue of outgoing messages
        '''
        while self.txMsgs:
            body, name = self.txMsgs.popleft() # duple (body dict, destination name)
            packed = self.packUxdTx(body)
            console.verbose("{0} sending\n{1}\n".format(self.name, body))
            self.txUxd(packed, name)

    def fetchParseUxdRx(self):
        '''
        Fetch from UXD deque next message tuple
        Parse raw message
        Return body if no errors
        Otherwise return None
        '''
        try:
            raw, sa, da = self.uxdRxes.popleft()
        except IndexError:
            return None

        console.verbose("{0} received raw message \n{1}\n".format(self.name, raw))

        if sa not in self.names:
            if not self.accept:
                emsg = "Unaccepted source ha = {0}. Dropping packet.".format(sa)
                print emsg
                return None

            name = yarding.Yard.nameFromHa(sa)
            yard = yarding.Yard(stack=self,
                                name=name,
                                ha=sa)
            self.addRemoteYard(yard)

        return self.parseUxdRx(raw) # deserialize

    def parseUxdRx(self, packed):
        '''
        Parse (deserialize message)
        '''
        body = None

        if (not packed.startswith('RAET\n') or raeting.HEAD_END not in packed):
            emsg = "Unrecognized packed body head"
            raise raeting.StackError(emsg)

        front, sep, back = packed.partition(raeting.HEAD_END)
        code, sep, kind = front.partition('\n')
        if kind not in [raeting.BODY_KIND_NAMES[raeting.bodyKinds.json]]:
            emsg = "Unrecognized packed body kind '{0}'".format(kind)
            raise raeting.StackError(emsg)

        kind = raeting.BODY_KINDS[kind]
        if kind == raeting.bodyKinds.json:
            body = json.loads(back, object_pairs_hook=odict)
            if not isinstance(body, Mapping):
                emsg = "Message body not a mapping."
                raise raeting.PacketError(emsg)

        return body

    def processUdpRx(self):
        '''
        Retrieve next message from stack receive queue if any and parse
        '''
        body = self.fetchParseUxdRx()
        if not body:
            return

        console.verbose("{0} received message data\n{1}\n".format(self.name, body))

        self.rxMsgs.append(body)

    def serviceUxdRx(self):
        '''
        Process all messages in .uxdRxes deque
        '''
        while self.uxdRxes:
            self.processUdpRx()




