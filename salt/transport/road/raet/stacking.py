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

try:
    import msgpack
except ImportError:
    mspack = None

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base import aiding
from ioflo.base import storing

from . import raeting
from . import nacling
from . import packeting
from . import estating
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
                 main=False,
                 version=raeting.VERSION,
                 store=None,
                 estate=None,
                 eid=None,
                 ha=("", raeting.RAET_PORT),
                 rxMsgs=None,
                 txMsgs=None,
                 udpRxes=None,
                 udpTxes=None,
                 road=None,
                 safe=None,
                 auto=None,
                 dirpath=None,
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
        self.estates = odict() # remote estates attached to this stack by eid
        self.eids = odict() # reverse lookup eid by estate.name
        self.transactions = odict() #transactions
        self.rxMsgs = rxMsgs if rxMsgs is not None else deque() # messages received
        self.txMsgs = txMsgs if txMsgs is not None else deque() # messages to transmit
        self.udpRxes = udpRxes if udpRxes is not None else deque() # udp packets received
        self.udpTxes = udpTxes if udpTxes is not None else deque() # udp packet to transmit

        self.road = road or keeping.RoadKeep(dirpath=dirpath,
                                             stackname=self.name)
        self.safe = safe or keeping.SafeKeep(dirpath=dirpath,
                                             stackname=self.name,
                                             auto=auto)
        kept = self.loadLocal() # local estate from saved data
        # local estate for this stack
        self.estate = kept or estate or estating.LocalEstate(stack=self,
                                                             eid=eid,
                                                             main=main,
                                                             ha=ha)
        self.estate.stack = self
        self.serverUdp = aiding.SocketUdpNb(ha=self.estate.ha, bufsize=raeting.MAX_MESSAGE_SIZE)
        self.serverUdp.reopen()  # open socket
        self.estate.ha = self.serverUdp.ha  # update estate host address after open
        self.dumpLocal() # save local estate data

        kepts = self.loadAllRemote() # remote estates from saved data
        for kept in kepts:
            self.addRemoteEstate(kept)
        self.dumpAllRemote() # save remote estate data

    def fetchRemoteEstateByHostPort(self, host, port):
        '''
        Search for remote estate with matching (host, port)
        Return estate if found Otherwise return None
        '''
        for estate in self.estates.values():
            if estate.host == host and estate.port == port:
                return estate

        return None

    def fetchRemoteEstateByKeys(self, sighex, prihex):
        '''
        Search for remote estate with matching (name, sighex, prihex)
        Return estate if found Otherwise return None
        '''
        for estate in self.estates.values():
            if (estate.signer.keyhex == sighex or
                estate.priver.keyhex == prihex):
                return estate

        return None

    def fetchRemoteEstateByName(self, name):
        '''
        Search for remote estate with matching name
        Return estate if found Otherwise return None
        '''
        return self.estates.get(self.eids.get(name))

    def addRemoteEstate(self, estate, eid=None):
        '''
        Add a remote estate to .estates
        '''
        if eid is None:
            eid = estate.eid

        if eid in self.estates:
            emsg = "Estate with id '{0}' alreadys exists".format(eid)
            raise raeting.StackError(emsg)
        estate.stack = self
        self.estates[eid] = estate
        if estate.name in self.eids:
            emsg = "Estate with name '{0}' alreadys exists".format(estate.name)
            raise raeting.StackError(emsg)
        self.eids[estate.name] = estate.eid

    def moveRemoteEstate(self, old, new):
        '''
        Move estate at key old eid to key new eid but keep same index
        '''
        if new in self.estates:
            emsg = "Cannot move, '{0}' already exists".format(new)
            raise raeting.StackError(emsg)

        if old not in self.estates:
            emsg = "Cannot move '{0}' does not exist".format(old)
            raise raeting.StackError(emsg)

        estate = self.estates[old]
        index = self.estates.keys().index(old)
        estate.eid = new
        self.eids[estate.name] = new
        del self.estates[old]
        self.estates.insert(index, estate.eid, estate)

    def renameRemoteEstate(self, old, new):
        '''
        rename estate with old name to new name but keep same index
        '''
        if new in self.eids:
            emsg = "Cannot rename, '{0}' already exists".format(new)
            raise raeting.StackError(emsg)

        if old not in self.eids:
            emsg = "Cannot rename '{0}' does not exist".format(old)
            raise raeting.StackError(emsg)

        eid = self.eids[old]
        estate = self.estates[eid]
        estate.name = new
        index = self.eids.keys().index(old)
        del self.eids[old]
        self.eids.insert(index, estate.name, estate.eid)

    def removeRemoteEstate(self, eid):
        '''
        Remove estate at key eid
        '''
        if eid not in self.estates:
            emsg = "Cannot remove, '{0}' does not exist".format(eid)
            raise raeting.StackError(emsg)

        estate = self.estates[eid]
        del self.estates[eid]
        del self.eids[estate.name]

    def clearLocal(self):
        '''
        Clear local keeps
        '''
        self.road.clearLocalData()
        self.safe.clearLocalData()

    def clearRemote(self, estate):
        '''
        Clear remote keeps of estate
        '''
        self.road.clearRemoteEstate()
        self.safe.clearRemoteEstate()

    def clearAllRemote(self):
        '''
        Clear all remote keeps
        '''
        self.road.clearAllRemoteData()
        self.safe.clearAllRemoteData()

    def dumpLocal(self):
        '''
        Dump keeps of local estate
        '''
        self.road.dumpLocalEstate(self.estate)
        self.safe.dumpLocalEstate(self.estate)

    def dumpRemote(self, estate):
        '''
        Dump keeps of estate
        '''
        self.road.dumpRemoteEstate(estate)
        self.safe.dumpRemoteEstate(estate)

    def dumpRemoteByEid(self, eid):
        '''
        Dump keeps of estate given by eid
        '''
        estate = self.estates.get(eid)
        if estate:
            self.dumpRemote(estate)

    def dumpAllRemote(self):
        '''
        Dump all remotes estates to keeps'''
        self.road.dumpAllRemoteEstates(self.estates.values())
        self.safe.dumpAllRemoteEstates(self.estates.values())

    def loadLocal(self):
        '''
        Load and Return local estate if keeps found
        '''
        road = self.road.loadLocalData()
        safe = self.safe.loadLocalData()
        if not road or not safe:
            return None
        estate = estating.LocalEstate(stack=self,
                                      eid=road['eid'],
                                      name=road['name'],
                                      main=road['main'],
                                      host=road['host'],
                                      port=road['port'],
                                      sid=road['sid'],
                                      sigkey=safe['sighex'],
                                      prikey=safe['prihex'],)
        return estate

    def loadAllRemote(self):
        '''
        Load and Return list of remote estates
        remote = estating.RemoteEstate( stack=self.stack,
                                        name=name,
                                        host=data['sh'],
                                        port=data['sp'],
                                        acceptance=acceptance,
                                        verkey=verhex,
                                        pubkey=pubhex,
                                        rsid=self.sid,
                                        rtid=self.tid, )
        self.stack.addRemoteEstate(remote)
        '''
        estates = []
        roads = self.road.loadAllRemoteData()
        safes = self.safe.loadAllRemoteData()
        if not roads or not safes:
            return []
        for key, road in roads.items():
            if key not in safes:
                continue
            safe = safes[key]
            estate = estating.RemoteEstate( stack=self,
                                            eid=road['eid'],
                                            name=road['name'],
                                            host=road['host'],
                                            port=road['port'],
                                            sid=road['sid'],
                                            rsid=road['rsid'],
                                            acceptance=safe['acceptance'],
                                            verkey=safe['verhex'],
                                            pubkey=safe['pubhex'],)
            estates.append(estate)
        return estates

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

    def txUdp(self, packed, deid):
        '''
        Queue duple of (packed, da) on stack transmit queue
        Where da is the ip destination (host,port) address associated with
        the estate with deid
        '''
        if deid not in self.estates:
            msg = "Invalid destination estate id '{0}'".format(deid)
            raise raeting.StackError(msg)
        self.udpTxes.append((packed, self.estates[deid].ha))

    def txMsg(self, msg, deid=None):
        '''
        Append duple (msg,deid) to .txMsgs deque
        If msg is not mapping then raises exception
        If deid is None then it will default to the first entry in .estates
        '''
        if not isinstance(msg, Mapping):
            emsg = "Invalid msg, not a mapping {0}".format(msg)
            raise raeting.StackError(emsg)
        self.txMsgs.append((msg, deid))

    transmit = txMsg

    def serviceTxMsg(self):
        '''
        Service .udpTxMsgs queue of outgoint udp messages for message transactions
        '''
        while self.txMsgs:
            body, deid = self.txMsgs.popleft() # duple (body dict, destination eid)
            self.message(body, deid)
            console.verbose("{0} sending\n{1}\n".format(self.name, body))

    def fetchParseUdpRx(self):
        '''
        Fetch from UDP deque next packet tuple
        Parse packet
        Return packet if verified and destination eid matches
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

        deid = packet.data['de']
        if deid != 0 and self.estate.eid != 0 and deid != self.estate.eid:
            emsg = "Invalid destination eid = {0}. Dropping packet.".format(deid)
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
        joinent.join() #assigns .reid here
        # need to perform the check for accepted status somewhere
        #joinent.accept() now in joinent.process()

    def allow(self, reid=None):
        '''
        Initiate allow transaction
        '''
        data = odict(hk=self.Hk, bk=raeting.bodyKinds.raw, fk=self.Fk)
        allower = transacting.Allower(stack=self, reid=reid, txData=data)
        allower.hello()

    def replyAllow(self, packet):
        '''
        Correspond to new allow transaction
        '''
        data = odict(hk=self.Hk, bk=raeting.bodyKinds.raw, fk=self.Fk)
        allowent = transacting.Allowent(stack=self,
                                        reid=packet.data['se'],
                                        sid=packet.data['si'],
                                        tid=packet.data['ti'],
                                        txData=data,
                                        rxPacket=packet)
        allowent.hello()

    def message(self, body=None, deid=None):
        '''
        Initiate message transaction
        '''
        data = odict(hk=self.Hk, bk=self.Bk, fk=self.Fk, ck=self.Ck)
        messenger = transacting.Messenger(stack=self, txData=data, reid=deid)
        messenger.message(body)

    def replyMessage(self, packet):
        '''
        Correspond to new Message transaction
        '''
        data = odict(hk=self.Hk, bk=self.Bk, fk=self.Fk, ck=self.Ck)
        messengent = transacting.Messengent(stack=self,
                                        reid=packet.data['se'],
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
    Pk = raeting.packKinds.json # serialization pack kind of Uxd message
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
        self.yard.ha = self.serverUxd.ha  # update estate host address after open

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
            emsg = "Estate with name '{0}' alreadys exists".format(name)
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
        change yard with old ha to new ha but keep same index
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
        the estate with name
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
            kind = self.Pk

        packed = ""
        if kind not in [raeting.packKinds.json, raeting.packKinds.pack]:
            emsg = "Invalid message pack kind '{0}'".format(kind)
            raise raeting.StackError(emsg)

        if kind == raeting.packKinds.json:
            head = 'RAET\njson\n\n'
            packed = "".join([head, json.dumps(body, separators=(',', ':'))])

        elif kind == raeting.packKinds.pack:
            if not msgpack:
                emsg = "Msgpack not installed."
                raise raeting.StackError(emsg)
            head = 'RAET\npack\n\n'
            packed = "".join([head, msgpack.dumps(body)])

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
        if kind not in [raeting.PACK_KIND_NAMES[raeting.packKinds.json],
                        raeting.PACK_KIND_NAMES[raeting.packKinds.pack]]:
            emsg = "Unrecognized message pack kind '{0}'".format(kind)
            raise raeting.StackError(emsg)

        kind = raeting.PACK_KINDS[kind]
        if kind == raeting.packKinds.json:
            body = json.loads(back, object_pairs_hook=odict)
            if not isinstance(body, Mapping):
                emsg = "Message body not a mapping."
                raise raeting.PacketError(emsg)
        elif kind == raeting.packKinds.pack:
            if not msgpack:
                emsg = "Msgpack not installed."
                raise raeting.StackError(emsg)
            body = msgpack.loads(back, object_pairs_hook=odict)
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




