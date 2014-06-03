# -*- coding: utf-8 -*-
'''
stacking.py raet protocol stacking classes
'''
# pylint: skip-file
# pylint: disable=W0611

# Import python libs
import socket
import os
import errno

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
from . import paging
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
    Hk = raeting.headKinds.raet # stack default
    Bk = raeting.bodyKinds.json # stack default
    Fk = raeting.footKinds.nacl # stack default
    Ck = raeting.coatKinds.nacl # stack default
    Bf = False # stack default for bcstflag
    Wf = False # stack default for waitflag

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
                 rxes=None,
                 txes=None,
                 road=None,
                 safe=None,
                 auto=None,
                 dirpath=None,
                 stats=None,
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
        self.rxes = rxes if rxes is not None else deque() # udp packets received
        self.txes = txes if txes is not None else deque() # udp packet to transmit
        self.stats = stats if stats is not None else odict() # udp statistics
        self.statTimer = aiding.StoreTimer(self.store)

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
        self.server = aiding.SocketUdpNb(ha=self.estate.ha, bufsize=raeting.UDP_MAX_PACKET_SIZE * 2)
        self.server.reopen()  # open socket
        self.estate.ha = self.server.ha  # update estate host address after open
        self.dumpLocal() # save local estate data

        kepts = self.loadAllRemote() # remote estates from saved data
        for kept in kepts:
            self.addRemote(kept)
        self.dumpAllRemote() # save remote estate data

    def fetchRemoteByHostPort(self, host, port):
        '''
        Search for remote estate with matching (host, port)
        Return estate if found Otherwise return None
        '''
        for estate in self.estates.values():
            if estate.host == host and estate.port == port:
                return estate

        return None

    def fetchRemoteByKeys(self, sighex, prihex):
        '''
        Search for remote estate with matching (name, sighex, prihex)
        Return estate if found Otherwise return None
        '''
        for estate in self.estates.values():
            if (estate.signer.keyhex == sighex or
                estate.priver.keyhex == prihex):
                return estate

        return None

    def fetchRemoteByName(self, name):
        '''
        Search for remote estate with matching name
        Return estate if found Otherwise return None
        '''
        return self.estates.get(self.eids.get(name))

    def addRemote(self, estate, eid=None):
        '''
        Add a remote estate to .estates
        '''
        if eid is None:
            eid = estate.eid

        if eid in self.estates:
            emsg = "Cannot add id '{0}' estate alreadys exists".format(eid)
            raise raeting.StackError(emsg)
        estate.stack = self
        self.estates[eid] = estate
        if estate.name in self.eids:
            emsg = "Cannot add name '{0}' estate alreadys exists".format(estate.name)
            raise raeting.StackError(emsg)
        self.eids[estate.name] = estate.eid

    def moveRemote(self, old, new):
        '''
        Move estate at key old eid to key new eid but keep same index
        '''
        if new in self.estates:
            emsg = "Cannot move, '{0}' estate already exists".format(new)
            raise raeting.StackError(emsg)

        if old not in self.estates:
            emsg = "Cannot move '{0}' estate does not exist".format(old)
            raise raeting.StackError(emsg)

        estate = self.estates[old]
        index = self.estates.keys().index(old)
        estate.eid = new
        self.eids[estate.name] = new
        del self.estates[old]
        self.estates.insert(index, estate.eid, estate)

    def renameRemote(self, old, new):
        '''
        rename estate with old name to new name but keep same index
        '''
        if new in self.eids:
            emsg = "Cannot rename, '{0}' estate already exists".format(new)
            raise raeting.StackError(emsg)

        if old not in self.eids:
            emsg = "Cannot rename '{0}' estate does not exist".format(old)
            raise raeting.StackError(emsg)

        eid = self.eids[old]
        estate = self.estates[eid]
        estate.name = new
        index = self.eids.keys().index(old)
        del self.eids[old]
        self.eids.insert(index, estate.name, estate.eid)

    def removeRemote(self, eid):
        '''
        Remove estate at key eid
        '''
        if eid not in self.estates:
            emsg = "Cannot remove, '{0}' estate does not exist".format(eid)
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

    def clearStats(self):
        '''
        Set all the stat counters to zero and reset the timer
        '''
        for key, value in self.stats.items():
            self.stats[key] = 0
        self.statTimer.restart()

    def clearStat(self, key):
        '''
        Set the specified state counter to zero
        '''
        if key in self.stats:
            self.stats[key] = 0

    def incStat(self, key, delta=1):
        '''
        Increment stat key counter by delta
        '''
        if key in self.stats:
            self.stats[key] += delta
        else:
            self.stats[key] = delta

    def updateStat(self, key, value):
        '''
        Set stat key to value
        '''
        self.stats[key] = value

    def serviceUdpRx(self):
        '''
        Service the UDP receive and fill the rxes deque
        '''
        if self.server:
            while True:
                rx, ra = self.server.receive()  # if no data the duple is ('',None)
                if not rx:  # no received data so break
                    break
                # triple = ( packet, source address, destination address)
                self.rxes.append((rx, ra, self.server.ha))

        return None

    def serviceRxes(self):
        '''
        Process all messages in .rxes deque
        '''
        while self.rxes:
            self.processUdpRx()

    def serviceTxMsgs(self):
        '''
        Service .txMsgs queue of outgoing  messages and start message transactions
        '''
        while self.txMsgs:
            body, deid = self.txMsgs.popleft() # duple (body dict, destination eid)
            self.message(body, deid)
            console.verbose("{0} sending\n{1}\n".format(self.name, body))

    def serviceTxes(self):
        '''
        Service the .txes deque to send Udp messages
        '''
        if self.server:
            laters = deque()
            while self.txes:
                tx, ta = self.txes.popleft()  # duple = (packet, destination address)
                try:
                    self.server.send(tx, ta)
                except socket.error as ex:
                    if ex.errno == errno.EAGAIN or ex.errno == errno.EWOULDBLOCK:
                        #busy with last message save it for later
                        laters.append((tx, ta))
                    else:
                        #console.verbose("socket.error = {0}\n".format(ex))
                        raise
            while laters:
                self.txes.append(laters.popleft())

    def serviceUdp(self):
        '''
        Service the UDP receive and transmit queues
        '''
        self.serviceUdpRx()
        self.serviceTxes()

    def serviceRx(self):
        '''
        Service:
           UDP Socket receive
           rxes queue
           process
        '''
        self.serviceUdpRx()
        self.serviceRxes()
        self.process()

    def serviceTx(self):
        '''
        Service:
           txMsgs queue
           txes queue and UDP Socket send
        '''
        self.serviceTxMsgs()
        self.serviceTxes()

    def serviceAll(self):
        '''
        Service or Process:
           UDP Socket receive
           rxes queue
           process
           txMsgs queue
           txes queue and UDP Socket send
        '''
        self.serviceUdpRx()
        self.serviceRxes()
        self.process()

        self.serviceTxMsgs()
        self.serviceTxes()

    def transmit(self, msg, deid=None):
        '''
        Append duple (msg,deid) to .txMsgs deque
        If msg is not mapping then raises exception
        If deid is None then it will default to the first entry in .estates
        '''
        if not isinstance(msg, Mapping):
            emsg = "Invalid msg, not a mapping {0}\n".format(msg)
            console.terse(emsg)
            self.incStat("invalid_transmit_body")
            return
        self.txMsgs.append((msg, deid))

    txMsg = transmit

    def txUdp(self, packed, deid):
        '''
        Queue duple of (packed, da) on stack transmit queue
        Where da is the ip destination (host,port) address associated with
        the estate with deid
        '''
        if deid not in self.estates:
            msg = "Invalid destination estate id '{0}'".format(deid)
            raise raeting.StackError(msg)
        self.txes.append((packed, self.estates[deid].ha))

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

        if packet.data['cf']: #correspondent to stale transaction
            self.stale(packet)
            return

        self.reply(packet)

    def fetchParseUdpRx(self):
        '''
        Fetch from UDP deque next packet tuple
        Parse packet
        Return packet if verified and destination eid matches
        Otherwise return None
        '''
        try:
            raw, sa, da = self.rxes.popleft()
        except IndexError:
            return None

        console.verbose("{0} received packet\n{1}\n".format(self.name, raw))

        packet = packeting.RxPacket(stack=self, packed=raw)
        try:
            packet.parseOuter()
        except raeting.PacketError as ex:
            console.terse(str(ex) + '\n')
            self.incStat('parsing_outer_error')
            return None

        deid = packet.data['de']
        if deid != 0 and self.estate.eid != 0 and deid != self.estate.eid:
            emsg = "Invalid destination eid = {0}. Dropping packet...\n".format(deid)
            console.concise( emsg)
            return None

        sh, sp = sa
        dh, dp = da
        packet.data.update(sh=sh, sp=sp, dh=dh, dp=dp)

        return packet # outer only has been parsed

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
            console.terse(str(ex) + '\n')
            self.incStat('parsing_inner_error')
            return None
        return packet

    def stale(self, packet):
        '''
        Initiate stale transaction in order to nack a stale correspondent packet
        '''
        data = odict(hk=self.Hk, bk=self.Bk)
        staler = transacting.Staler(stack=self,
                                    kind=packet.data['tk'],
                                    reid=packet.data['se'],
                                    sid=packet.data['si'],
                                    tid=packet.data['ti'],
                                    txData=data,
                                    rxPacket=packet)
        staler.nack()

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
        messenger = transacting.Messenger(stack=self,
                                          txData=data,
                                          reid=deid,
                                          bcst=self.Bf,
                                          wait=self.Wf)
        messenger.message(body)

    def replyMessage(self, packet):
        '''
        Correspond to new Message transaction
        '''
        data = odict(hk=self.Hk, bk=self.Bk, fk=self.Fk, ck=self.Ck)
        messengent = transacting.Messengent(stack=self,
                                        reid=packet.data['se'],
                                        bcst=packet.data['bf'],
                                        wait=packet.data['wf'],
                                        sid=packet.data['si'],
                                        tid=packet.data['ti'],
                                        txData=data,
                                        rxPacket=packet)
        messengent.message()

    def nackStale(self, packet):
        '''
        Send nack to stale correspondent packet
        '''
        body = odict()
        txData = packet.data
        ha = (packet.data['sh'], packet.data['sp'])
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.nack,
                                    embody=body,
                                    data=txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(str(ex) + '\n')
            self.incStat("packing_error")
            return

        self.txes.append((packet.packed, ha))

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
                 rxes = None,
                 txes = None,
                 lane=None,
                 accept=None,
                 dirpath=None,
                 stats=None,
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
        self.yard = yard or yarding.LocalYard(stack=self,
                                         name=yardname,
                                         yid=yid,
                                         ha=ha,
                                         prefix=lanename,
                                         dirpath=dirpath)
        self.books = odict()
        self.rxMsgs = rxMsgs if rxMsgs is not None else deque() # messages received
        self.txMsgs = txMsgs if txMsgs is not None else deque() # messages to transmit
        self.rxes = rxes if rxes is not None else deque() # uxd packets received
        self.txes = txes if txes is not None else deque() # uxd packets to transmit
        self.stats = stats if stats is not None else odict() # udp statistics
        self.statTimer = aiding.StoreTimer(self.store)

        self.lane = lane # or keeping.LaneKeep()
        self.accept = self.Accept if accept is None else accept #accept uxd msg if not in lane
        self.server = aiding.SocketUxdNb(ha=self.yard.ha, bufsize=raeting.UXD_MAX_PACKET_SIZE * 2)
        self.server.reopen()  # open socket
        self.yard.ha = self.server.ha  # update estate host address after open
        #self.lane.dumpLocalLane(self.yard)

    def fetchRemoteByHa(self, ha):
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
            emsg = "Cannot add '{0}' yard alreadys exists".format(name)
            raise raeting.StackError(emsg)
        yard.stack = self
        self.yards[name] = yard
        if yard.ha in self.names or yard.ha == self.yard.ha:
            emsg = "Cannot add ha '{0}' yard alreadys exists".format(yard.ha)
            raise raeting.StackError(emsg)
        self.names[yard.ha] = yard.name

    def moveRemote(self, old, new):
        '''
        Move yard at key old name to key new name but keep same index
        '''
        if new in self.yards:
            emsg = "Cannot move, '{0}' yard already exists".format(new)
            raise raeting.StackError(emsg)

        if old not in self.yards:
            emsg = "Cannot move '{0}' yard does not exist".format(old)
            raise raeting.StackError(emsg)

        yard = self.yards[old]
        index = self.yards.keys().index(old)
        yard.name = new
        self.names[yard.ha] = new
        del self.yards[old]
        self.yards.insert(index, yard.name, yard)

    def rehaRemote(self, old, new):
        '''
        change yard with old ha to new ha but keep same index
        '''
        if new in self.names:
            emsg = "Cannot reha, '{0}' yard already exists".format(new)
            raise raeting.StackError(emsg)

        if old not in self.names:
            emsg = "Cannot reha '{0}' yard does not exist".format(old)
            raise raeting.StackError(emsg)

        name = self.names[old]
        yard = self.yards[name]
        yard.ha = new
        index = self.names.keys().index(old)
        del self.names[old]
        self.yards.insert(index, yard.ha, yard.name)

    def removeRemote(self, name):
        '''
        Remove yard at key name
        '''
        if name not in self.yards:
            emsg = "Cannot remove, '{0}' yard does not exist".format(name)
            raise raeting.StackError(emsg)

        yard = self.yards[name]
        del self.yards[name]
        del self.names[yard.ha]

    def addBook(self, index, book):
        '''
        Safely add book at index If not already there
        '''
        self.books[index] = book
        console.verbose( "Added book to {0} at '{1}'\n".format(self.name, index))

    def removeBook(self, index, book=None):
        '''
        Safely remove book at index If book identity same
        If book is None then remove without comparing identity
        '''
        if index in self.books:
            if book:
                if book is self.books[index]:
                    del  self.books[index]
            else:
                del self.books[index]

    def clearStats(self):
        '''
        Set all the stat counters to zero and reset the timer
        '''
        for key, value in self.stats.items():
            self.stats[key] = 0
        self.statTimer.restart()

    def clearStat(self, key):
        '''
        Set the specified state counter to zero
        '''
        if key in self.stats:
            self.stats[key] = 0

    def incStat(self, key, delta=1):
        '''
        Increment stat key counter by delta
        '''
        if key in self.stats:
            self.stats[key] += delta
        else:
            self.stats[key] = delta

    def updateStat(self, key, value):
        '''
        Set stat key to value
        '''
        self.stats[key] = value

    def serviceUxdRx(self):
        '''
        Service the Uxd receive and fill the .rxes deque
        '''
        if self.server:
            while True:
                rx, ra = self.server.receive()  # if no data the duple is ('',None)
                if not rx:  # no received data so break
                    break
                # triple = ( packet, source address, destination address)
                self.rxes.append((rx, ra, self.server.ha))

    def serviceRxes(self):
        '''
        Process all messages in .rxes deque
        '''
        while self.rxes:
            self.processUxdRx()

    def serviceTxMsgs(self):
        '''
        Service .txMsgs queue of outgoing messages
        '''
        while self.txMsgs:
            body, name = self.txMsgs.popleft() # duple (body dict, destination name)
            self.message(body, name)
            console.verbose("{0} sending\n{1}\n".format(self.name, body))

    def serviceTxes(self):
        '''
        Service the .txes deque to send Uxd messages
        '''
        if self.server:
            laters = deque()
            blocks = []

            while self.txes:
                tx, ta = self.txes.popleft()  # duple = (packet, destination address)

                if ta in blocks: # already blocked on this iteration
                    laters.append((tx, ta)) # keep sequential
                    continue

                try:
                    self.server.send(tx, ta)
                except socket.error as ex:
                    if ex.errno == errno.ECONNREFUSED:
                        console.terse("socket.error = {0}\n".format(ex))
                        self.incStat("stale_transmit_yard")
                        yard = self.fetchRemoteByHa(ta)
                        if yard:
                            self.removeRemote(yard.name)
                            console.terse("Reaped yard {0}\n".format(yard.name))
                    elif ex.errno == errno.EAGAIN or ex.errno == errno.EWOULDBLOCK:
                        #busy with last message save it for later
                        laters.append((tx, ta))
                        blocks.append(ta)

                    else:
                        #console.verbose("socket.error = {0}\n".format(ex))
                        raise
            while laters:
                self.txes.append(laters.popleft())

    def serviceUxd(self):
        '''
        Service the UXD receive and transmit queues
        '''
        self.serviceUxdRx()
        self.serviceTxes()

    def serviceRx(self):
        '''
        Service:
           Uxd Socket receive
           rxes queue
        '''
        self.serviceUxdRx()
        self.serviceRxes()

    def serviceTx(self):
        '''
        Service:
           txMsgs deque
           txes deque and send Uxd messages
        '''
        self.serviceTxMsgs()
        self.serviceTxes()

    def serviceAll(self):
        '''
        Service or Process:
           Uxd Socket receive
           rxes queue
           txMsgs queue
           txes queue and Uxd Socket send
        '''
        self.serviceUxdRx()
        self.serviceRxes()
        self.serviceTxMsgs()
        self.serviceTxes()

    def txUxd(self, packed, name):
        '''
        Queue duple of (packed, da) on stack .txes queue
        Where da is the uxd destination address associated with
        the yard with name
        If name is None then it will default to the first entry in .yards
        '''
        if name is None:
            if not self.yards:
                emsg = "No yard to send to\n"
                console.terse(emsg)
                self.incStat("invalid_destination_yard")
                return
            name = self.yards.values()[0].name
        if name not in self.yards:
            msg = "Invalid destination yard name '{0}'".format(name)
            console.terse(msg + '\n')
            self.incStat("invalid_destination_yard")
            return
        self.txes.append((packed, self.yards[name].ha))

    def transmit(self, msg, name=None):
        '''
        Append duple (msg, name) to .txMsgs deque
        If msg is not mapping then raises exception
        If name is None then txUxd will supply default
        '''
        if not isinstance(msg, Mapping):
            emsg = "Invalid msg, not a mapping {0}\n".format(msg)
            console.terse(emsg)
            self.incStat("invalid_transmit_body")
            return
        self.txMsgs.append((msg, name))

    txMsg = transmit # alias

    def message(self, body, name):
        '''
        Sends message body to yard name and manages paging of long messages
        '''
        if name is None:
            if not self.yards:
                emsg = "No yard to send to\n"
                console.terse(emsg)
                self.incStat("invalid_destination_yard")
                return
            name = self.yards.values()[0].name
        if name not in self.yards:
            emsg = "Invalid destination yard name '{0}'\n".format(name)
            console.terse(emsg)
            self.incStat("invalid_destination_yard")
            return
        remote = self.yards[name]
        data = odict(syn=self.yard.name, dyn=remote.name, mid=remote.nextMid())
        book = paging.TxBook(data=data, body=body, kind=self.Pk)
        try:
            book.pack()
        except raeting.PageError as ex:
            console.terse(str(ex) + '\n')
            self.incStat("packing_error")
            return

        print "Pages {0}".format(len(book.pages))

        for page in book.pages:
            self.txes.append((page.packed, remote.ha))

    def processUxdRx(self):
        '''
        Retrieve next page from stack receive queue if any and parse
        '''
        page = self.fetchParseUxdRx()
        if not page:
            return

        console.verbose("{0} received page data\n{1}\n".format(self.name, page.data))
        console.verbose("{0} received page index = '{1}'\n".format(self.name, page.index))

        if page.paginated:
            book = self.books.get(page.index)
            if not book:
                book = paging.RxBook(stack=self)
                self.addBook(page.index, book)
            body = book.parse(page)
            if body is None: #not done yet
                return
            self.removeBook(book.index)
        else:
            body = page.data

        self.rxMsgs.append(body)

    def fetchParseUxdRx(self):
        '''
        Fetch from UXD deque next message tuple
        Parse raw message
        Return body if no errors
        Otherwise return None
        '''
        try:
            raw, sa, da = self.rxes.popleft()
        except IndexError:
            return None

        console.verbose("{0} received raw message \n{1}\n".format(self.name, raw))

        if sa not in self.names:
            if not self.accept:
                emsg = "Unaccepted source ha = {0}. Dropping packet...\n".format(sa)
                console.terse(emsg)
                self.incStat('unaccepted_source_yard')
                return None
            try:
                self.addRemoteYard(yarding.RemoteYard(ha=sa))
            except raeting.StackError as ex:
                console.terse(str(ex) + '\n')
                self.incStat('invalid_source_yard')
                return None

        page = paging.RxPage(packed=raw)
        page.parse()
        return page

