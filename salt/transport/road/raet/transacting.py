# -*- coding: utf-8 -*-
'''
stacking.py raet protocol stacking classes
'''
# pylint: skip-file
# pylint: disable=W0611

# Import python libs
import socket
import binascii
import struct

try:
    import simplejson as json
except ImportError:
    import json

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base import aiding

from . import raeting
from . import nacling
from . import packeting
from . import estating

from ioflo.base.consoling import getConsole
console = getConsole()


class Transaction(object):
    '''
    RAET protocol transaction class
    '''
    Timeout =  5.0 # default timeout

    def __init__(self, stack=None, kind=None, timeout=None,
                 reid=None, rmt=False, bcst=False, sid=None, tid=None,
                 txData=None, txPacket=None, rxPacket=None):
        '''
        Setup Transaction instance
        timeout of 0.0 means no timeout go forever
        '''
        self.stack = stack
        self.kind = kind or raeting.PACKET_DEFAULTS['tk']

        if timeout is None:
            timeout = self.Timeout
        self.timeout = timeout
        self.timer = aiding.StoreTimer(self.stack.store, duration=self.timeout)

        # local estate is the .stack.estate
        self.reid = reid  # remote estate eid

        self.rmt = rmt
        self.bcst = bcst

        self.sid = sid
        self.tid = tid

        self.txData = txData or odict() # data used to prepare last txPacket
        self.txPacket = txPacket  # last tx packet needed for retries
        self.rxPacket = rxPacket  # last rx packet needed for index

    @property
    def index(self):
        '''
        Property is transaction tuple (rf, le, re, si, ti, bf,)
        '''
        le = self.stack.estate.eid
        if le == 0: #bootstapping onto channel use ha
            le = self.stack.estate.ha
        re = self.reid
        if re == 0: #bootstapping onto channel use ha
            re = self.stack.estates[self.reid].ha
        return ((self.rmt, le, re, self.sid, self.tid, self.bcst,))

    def process(self):
        '''
        Process time based handling of transaction like timeout or retries
        '''
        pass

    def receive(self, packet):
        '''
        Process received packet Subclasses should super call this
        '''
        self.rxPacket = packet

    def transmit(self, packet):
        '''
        Queue tx duple on stack transmit queue
        '''
        try:
            self.stack.txUdp(packet.packed, self.reid)
        except raeting.StackError as ex:
            console.terse(ex + '\n')
            self.stack.incStat(self.statKey())
            self.remove(packet.index)
            return
        self.txPacket = packet

    def add(self, index=None):
        '''
        Add self to stack transactions
        '''
        if not index:
            index = self.index
        self.stack.addTransaction(index, self)

    def remove(self, index=None):
        '''
        Remove self from stack transactions
        '''
        if not index:
            index = self.index
        self.stack.removeTransaction(index, transaction=self)

    def statKey(self):
        '''
        Return the stat name key from class name
        '''
        return ("{0}_transaction_failure".format(self.__class__.__name__.lower()))

class Initiator(Transaction):
    '''
    RAET protocol initiator transaction class
    '''
    def __init__(self, **kwa):
        '''
        Setup Transaction instance
        '''
        kwa['rmt'] = False  # force rmt to False
        super(Initiator, self).__init__(**kwa)

    def process(self):
        '''
        Process time based handling of transaction like timeout or retries
        '''
        if self.timeout > 0.0 and self.timer.expired:
            self.stack.removeTransaction(self.index, transaction=self)

class Correspondent(Transaction):
    '''
    RAET protocol correspondent transaction class
    '''
    Requireds = ['sid', 'tid', 'rxPacket']

    def __init__(self, **kwa):
        '''
        Setup Transaction instance
        '''
        kwa['rmt'] = True  # force rmt to True

        missing = []
        for arg in self.Requireds:
            if arg not in kwa:
                missing.append(arg)
        if missing:
            emsg = "Missing required keyword arguments: '{0}'".format(missing)
            raise TypeError(emsg)

        super(Correspondent, self).__init__(**kwa)

class Joiner(Initiator):
    '''
    RAET protocol Joiner Initiator class Dual of Joinent
    '''
    RedoTimeoutMin = 1.0 # initial timeout
    RedoTimeoutMax = 4.0 # max timeout


    def __init__(self, mha = None, redoTimeoutMin=None, redoTimeoutMax=None, **kwa):
        '''
        Setup Transaction instance
        '''
        kwa['kind'] = raeting.trnsKinds.join
        super(Joiner, self).__init__(**kwa)

        if mha is None:
            mha = ('127.0.0.1', raeting.RAET_PORT)

        self.redoTimeoutMax = redoTimeoutMax or self.RedoTimeoutMax
        self.redoTimeoutMin = redoTimeoutMin or self.RedoTimeoutMin
        self.redoTimer = aiding.StoreTimer(self.stack.store,
                                           duration=self.redoTimeoutMin)

        if self.reid is None:
            if not self.stack.estates: # no channel master so make one
                master = estating.RemoteEstate(eid=0, ha=mha)
                try:
                    self.stack.addRemote(master)
                except raeting.StackError as ex:
                    console.terse(ex + '\n')
                    self.stack.incStat(self.statKey())
                    return

            self.reid = self.stack.estates.values()[0].eid # zeroth is channel master
        self.sid = 0
        self.tid = self.stack.estates[self.reid].nextTid()
        self.prep()
        self.add(self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Joiner, self).receive(packet) #  self.rxPacket = packet

        if packet.data['tk'] == raeting.trnsKinds.join:
            if packet.data['pk'] == raeting.pcktKinds.ack: #pending
                self.pend()  #set timer for redo
            elif packet.data['pk'] == raeting.pcktKinds.response:
                self.accept()
            elif packet.data['pk'] == raeting.pcktKinds.nack: #rejected
                self.rejected()

    def process(self):
        '''
        Perform time based processing of transaction
        '''
        if self.timeout > 0.0 and self.timer.expired:
            if self.txPacket and self.txPacket.data['pk'] == raeting.pcktKinds.request:
                self.remove(self.txPacket.index) #index changes after accept
            else:
                self.remove(self.index) # in case never sent txPacket
            console.concise("Joiner timed out at {0}\n".format(self.stack.store.stamp))
            return

        # need keep sending join until accepted or timed out
        if self.redoTimer.expired:
            duration = min(
                        max(self.redoTimeoutMin,
                              self.redoTimer.duration) * 2.0,
                        self.redoTimeoutMin)
            self.redoTimer.restart(duration=duration)
            if (self.txPacket and
                    self.txPacket.data['pk'] == raeting.pcktKinds.request):
                self.transmit(self.txPacket) #redo
                console.concise("Joiner Redo Join at {0}\n".format(self.stack.store.stamp))


    def prep(self):
        '''
        Prepare .txData
        '''
        self.txData.update( sh=self.stack.estate.host,
                            sp=self.stack.estate.port,
                            dh=self.stack.estates[self.reid].host,
                            dp=self.stack.estates[self.reid].port,
                            se=self.stack.estate.eid,
                            de=self.reid,
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid,
                            ck=raeting.coatKinds.nada,
                            fk=raeting.footKinds.nada)

    def join(self):
        '''
        Send join request
        '''
        if self.reid not in self.stack.estates:
            emsg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat(self.statKey())
            self.remove()
            return

        body = odict([('name', self.stack.estate.name),
                      ('verhex', self.stack.estate.signer.verhex),
                      ('pubhex', self.stack.estate.priver.pubhex)])
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.request,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove()
            return
        self.transmit(packet)
        console.concise("Joiner Do Join at {0}\n".format(self.stack.store.stamp))

    def pend(self):
        '''
        Process ack to join packet
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        pass

    def accept(self):
        '''
        Perform acceptance in response to join response packet
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        leid = body.get('leid')
        if not leid:
            emsg = "Missing local estate id in accept packet"
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_accept')
            self.remove(self.txPacket.index)
            return

        reid = body.get('reid')
        if not reid:
            emsg = "Missing remote estate id in accept packet"
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_accept')
            self.remove(self.txPacket.index)
            return

        name = body.get('name')
        if not name:
            emsg = "Missing remote name in accept packet"
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_accept')
            self.remove(self.txPacket.index)
            return

        verhex = body.get('verhex')
        if not verhex:
            emsg = "Missing remote verifier key in accept packet"
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_accept')
            self.remove(self.txPacket.index)
            return

        pubhex = body.get('pubhex')
        if not pubhex:
            emsg = "Missing remote crypt key in accept packet"
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_accept')
            self.remove(self.txPacket.index)
            return

        self.stack.estate.eid = leid
        self.stack.dumpLocal()

        remote = self.stack.estates[self.reid]

        if remote.eid != reid: #move remote estate to new index
            try:
                self.stack.moveRemote(old=remote.eid, new=reid)
            except raeting.StackError as ex:
                console.terse(ex + '\n')
                self.stack.incStat(self.statKey())
                self.remove(self.txPacket.index)
                return
        if remote.name != name: # rename remote estate to new name
            try:
                self.stack.renameRemote(old=remote.name, new=name)
            except raeting.StackError as ex:
                console.terse(ex + '\n')
                self.stack.incStat(self.statKey())
                self.remove(self.txPacket.index)
                return

        self.reid = reid

        # we are assuming for now that the joiner cannot talk peer to peer only
        # to main estate otherwise we need to ensure unique eid, name, and ha on road

        # check if remote keys of main estate are accepted here
        status = self.stack.safe.statusRemoteEstate(remote,
                                                    verhex=verhex,
                                                    pubhex=pubhex,
                                                    main=False)
        if status == raeting.acceptances.rejected:
            self.nackAccept()
        else:
            remote.joined = True #accepted
            remote.nextSid()
            self.ackAccept()

        self.stack.dumpRemote(remote)

    def rejected(self):
        '''
        Process nack to join packet
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        self.remove(self.txPacket.index)
        console.terse("Joiner Rejected at {0}\n".format(self.stack.store.stamp))
        self.stack.incStat(self.statKey())

    def ackAccept(self):
        '''
        Send ack to accept response
        '''
        if self.reid not in self.stack.estates:
            emsg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_remote_eid')
            self.remove(self.txPacket.index)
            return

        body = odict()
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.ack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove(self.txPacket.index)
            return

        self.transmit(packet)
        self.remove(self.rxPacket.index)
        console.concise("Joiner Do Accept at {0}\n".format(self.stack.store.stamp))
        self.stack.incStat("join_initiate_complete")

    def nackAccept(self):
        '''
        Send nack to accept response
        '''
        if self.reid not in self.stack.estates:
            emsg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_remote_eid')
            self.remove(self.txPacket.index)
            return

        body = odict()
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.nack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove(self.txPacket.index)
            return

        self.transmit(packet)
        self.remove(self.txPacket.index)
        console.terse("Joiner Do Reject at {0}\n".format(self.stack.store.stamp))
        self.stack.incStat(self.statKey())


class Joinent(Correspondent):
    '''
    RAET protocol Joinent transaction class, dual of Joiner
    '''
    RedoTimeoutMin = 0.1 # initial timeout
    RedoTimeoutMax = 2.0 # max timeout

    def __init__(self, redoTimeoutMin=None, redoTimeoutMax=None, **kwa):
        '''
        Setup Transaction instance
        '''
        kwa['kind'] = raeting.trnsKinds.join
        super(Joinent, self).__init__(**kwa)

        self.redoTimeoutMax = redoTimeoutMax or self.RedoTimeoutMax
        self.redoTimeoutMin = redoTimeoutMin or self.RedoTimeoutMin
        self.redoTimer = aiding.StoreTimer(self.stack.store, duration=0.0)

        self.prep()
        # Since corresponding bootstrap transaction use packet.index not self.index
        self.add(self.rxPacket.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Joinent, self).receive(packet) #  self.rxPacket = packet

        if packet.data['tk'] == raeting.trnsKinds.join:
            if packet.data['pk'] == raeting.pcktKinds.ack: #accepted by joiner
                self.joined()

    def process(self):
        '''
        Perform time based processing of transaction

        '''
        if self.timeout > 0.0 and self.timer.expired:
            self.nackJoin()
            console.concise("Joinent timed out at {0}\n".format(self.stack.store.stamp))
            return

        # need to perform the check for accepted status and then send accept
        if self.redoTimer.expired:
            duration = min(
                        max(self.redoTimeoutMin,
                              self.redoTimer.duration) * 2.0,
                        self.redoTimeoutMax)
            self.redoTimer.restart(duration=duration)

            if (self.txPacket and
                    self.txPacket.data['pk'] == raeting.pcktKinds.response):

                self.transmit(self.txPacket) #redo
                console.concise("Joinent Redo Accept at {0}\n".format(self.stack.store.stamp))
            else: #check to see if status has changed to accept
                remote = self.stack.estates[self.reid]
                if remote:
                    data = self.stack.safe.loadRemoteEstate(remote)
                    if data:
                        status = self.stack.safe.statusRemoteEstate(remote,
                                                                    data['verhex'],
                                                                    data['pubhex'])
                        if status == raeting.acceptances.accepted:
                            self.accept()


    def prep(self):
        '''
        Prepare .txData
        '''
        #since bootstrap transaction use the reversed seid and deid from packet
        self.txData.update( sh=self.stack.estate.host,
                    sp=self.stack.estate.port,
                    se=self.rxPacket.data['de'],
                    de=self.rxPacket.data['se'],
                    tk=self.kind,
                    cf=self.rmt,
                    bf=self.bcst,
                    si=self.sid,
                    ti=self.tid,
                    ck=raeting.coatKinds.nada,
                    fk=raeting.footKinds.nada,)

    def join(self):
        '''
        Process join packet
        Respond based on acceptance status of remote estate.



        Rules for Colliding Estates
        Apply the rules to ensure no colliding estates on (host, port)
        If matching name estate found then return
        Rules:
            Only one estate with given eid is allowed on road
            Only one estate with given name is allowed on road.
            Only one estate with given ha on road is allowed on road.

            Are multiple estates with same keys but different name (ha) allowed?
            Current logic ignores same keys or not

        Since creating new estate assigns unique eid,
        we are looking for preexisting estates with any eid.

        Processing steps:
        I) Search remote estates for matching name
            A) Found remote
                1) HA not match
                    Search remotes for other matching HA but different name
                    If found other delete
                Reuse found remote to be updated and joined

            B) Not found
                Search remotes for other matching HA
                If found delete for now
                Create new remote and update
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        name = body.get('name')
        if not name:
            emsg = "Missing remote name in join packet"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_join')
            self.remove(self.rxPacket.index)
            return
            #raise raeting.TransactionError(emsg)

        verhex = body.get('verhex')
        if not verhex:
            emsg = "Missing remote verifier key in join packet"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_join')
            self.remove(self.rxPacket.index)
            return
            #raise raeting.TransactionError(emsg)

        pubhex = body.get('pubhex')
        if not pubhex:
            emsg = "Missing remote crypt key in join packet"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_join')
            self.remove(self.rxPacket.index)
            return
            #raise raeting.TransactionError(emsg)

        host = data['sh']
        port = data['sp']
        self.txData.update( dh=host, dp=port,) # responses use received host port

        remote = self.stack.fetchRemoteByName(name)
        if remote:
            if not (host == remote.host and port == remote.port):
                other = self.stack.fetchRemoteByHostPort(host, port)
                if other and other is not remote: #may need to terminate transactions
                    try:
                        self.stack.removeRemote(other.eid)
                    except raeting.StackError as ex:
                        console.terse(ex + '\n')
                        self.stack.incStat(self.statKey())
                        self.remove(self.rxPacket.index)
                        return
                remote.host = host
                remote.port = port
            remote.rsid = self.sid
            remote.rtid = self.tid
            status = self.stack.safe.statusRemoteEstate(remote,
                                                        verhex=verhex,
                                                        pubhex=pubhex)
        else:
            other = self.stack.fetchRemoteByHostPort(host, port)
            if other: #may need to terminate transactions
                try:
                    self.stack.removeRemote(other.eid)
                except raeting.StackError as ex:
                    console.terse(ex + '\n')
                    self.stack.incStat(self.statKey())
                    self.remove(self.rxPacket.index)
                    return

            remote = estating.RemoteEstate( stack=self.stack,
                                            name=name,
                                            host=host,
                                            port=port,
                                            acceptance=None,
                                            verkey=verhex,
                                            pubkey=pubhex,
                                            rsid=self.sid,
                                            rtid=self.tid, )
            try:
                self.stack.addRemote(remote) #provisionally add .accepted is None
            except raeting.StackError as ex:
                console.terse(ex + '\n')
                self.stack.incStat(self.statKey())
                self.remove(self.rxPacket.index)
                return
            status = self.stack.safe.statusRemoteEstate(remote,
                                                        verhex=verhex,
                                                        pubhex=pubhex)

        self.stack.dumpRemote(remote)
        self.reid = remote.eid # auto generated at instance creation above

        if status == None or status == raeting.acceptances.pending:
            self.ackJoin()
        elif status == raeting.acceptances.accepted:
            duration = min(
                         max(self.redoTimeoutMin,
                            self.redoTimer.duration) * 2.0,
                         self.redoTimeoutMax)
            self.redoTimer.restart(duration=duration)
            self.accept()
        else:
            self.nackJoin()
            emsg = "Estate {0} eid {1} keys rejected\n".format(
                            remote.name, remote.eid)
            console.terse(emsg)

    def ackJoin(self):
        '''
        Send ack to join request
        '''
        if self.reid not in self.stack.estates:
            emsg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_remote_eid')
            self.remove(self.rxPacket.index)
            return

        #since bootstrap transaction use updated self.reid
        #self.txData.update( dh=self.stack.estates[self.reid].host,
                            #dp=self.stack.estates[self.reid].port,)
        body = odict()
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.ack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove(self.rxPacket.index)
            return

        self.transmit(packet)
        console.concise("Joinent Pending Accept at {0}\n".format(self.stack.store.stamp))

    def accept(self):
        '''
        Send accept response to join request
        '''
        if self.reid not in self.stack.estates:
            emsg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_remote_eid')
            self.remove(self.rxPacket.index)
            return

        remote = self.stack.estates[self.reid]

        body = odict([ ('leid', self.reid),
                       ('reid', self.stack.estate.eid),
                       ('name', self.stack.estate.name),
                       ('verhex', self.stack.estate.signer.verhex),
                       ('pubhex', self.stack.estate.priver.pubhex)])
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.response,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove(self.rxPacket.index)
            return

        self.transmit(packet)
        console.concise("Joinent Do Accept at {0}\n".format(self.stack.store.stamp))

    def joined(self):
        '''
        process ack to accept response
        '''
        remote = self.stack.estates[self.reid]
        remote.joined = True # accepted
        remote.nextSid()
        self.stack.dumpRemote(remote)
        self.remove(self.rxPacket.index)

        self.stack.incStat("join_correspond_complete")

    def nackJoin(self):
        '''
        Send nack to join request
        '''
        if self.reid not in self.stack.estates:
            emsg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_remote_eid')
            self.remove(self.rxPacket.index)
            return

        body = odict()
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.nack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove(self.rxPacket.index)
            return

        self.transmit(packet)
        self.remove(self.rxPacket.index)
        console.terse("Joinent Reject at {0}\n".format(self.stack.store.stamp))
        self.stack.incStat(self.statKey())


class Allower(Initiator):
    '''
    RAET protocol Allower Initiator class Dual of Allowent
    CurveCP handshake
    '''
    Timeout = 2.0
    RedoTimeoutMin = 0.25 # initial timeout
    RedoTimeoutMax = 1.0 # max timeout

    def __init__(self, redoTimeoutMin=None, redoTimeoutMax=None, **kwa):
        '''
        Setup instance
        '''
        kwa['kind'] = raeting.trnsKinds.allow
        super(Allower, self).__init__(**kwa)
        self.oreo = None # cookie from correspondent needed until handshake completed

        self.redoTimeoutMax = redoTimeoutMax or self.RedoTimeoutMax
        self.redoTimeoutMin = redoTimeoutMin or self.RedoTimeoutMin
        self.redoTimer = aiding.StoreTimer(self.stack.store,
                                           duration=self.redoTimeoutMin)

        if self.reid is None:
            self.reid = self.stack.estates.values()[0].eid # zeroth is channel master
        remote = self.stack.estates[self.reid]
        if not remote.joined:
            emsg = "Must be joined first"
            console.terse(emsg + '\n')
            self.stack.incStat('unjoined_allow_attempt')
            return
            #raise raeting.TransactionError(emsg)
        remote.refresh() # refresh short term keys and .allowed
        self.sid = remote.sid
        self.tid = remote.nextTid()
        self.prep() # prepare .txData
        self.add(self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Allower, self).receive(packet) #  self.rxPacket = packet

        if packet.data['tk'] == raeting.trnsKinds.allow:
            if packet.data['pk'] == raeting.pcktKinds.cookie:
                self.cookie()
            elif packet.data['pk'] == raeting.pcktKinds.ack:
                self.allow()

    def process(self):
        '''
        Perform time based processing of transaction
        '''
        if self.timeout > 0.0 and self.timer.expired:
            self.remove()
            console.concise("Allower timed out at {0}\n".format(self.stack.store.stamp))
            return

        # need keep sending join until accepted or timed out
        if self.redoTimer.expired:
            duration = min(
                         max(self.redoTimeoutMin,
                              self.redoTimer.duration) * 2.0,
                         self.redoTimeoutMin)
            self.redoTimer.restart(duration=duration)
            if self.txPacket:
                if self.txPacket.data['pk'] == raeting.pcktKinds.hello:
                    self.transmit(self.txPacket) # redo
                    console.concise("Allower Redo Hello at {0}\n".format(self.stack.store.stamp))

                if self.txPacket.data['pk'] == raeting.pcktKinds.initiate:
                    self.transmit(self.txPacket) # redo
                    console.concise("Allower Redo Initiate at {0}\n".format(self.stack.store.stamp))

                if self.txPacket.data['pk'] == raeting.pcktKinds.ack:
                    self.transmit(self.txPacket) # redo
                    console.concise("Allower Redo Ack Final at {0}\n".format(self.stack.store.stamp))


    def prep(self):
        '''
        Prepare .txData
        '''
        remote = self.stack.estates[self.reid]
        self.txData.update( sh=self.stack.estate.host,
                            sp=self.stack.estate.port,
                            dh=remote.host,
                            dp=remote.port,
                            se=self.stack.estate.eid,
                            de=self.reid,
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid, )

    def hello(self):
        '''
        Send hello request
        '''
        if self.reid not in self.stack.estates:
            emsg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_remote_eid')
            self.remove()
            return

        remote = self.stack.estates[self.reid]
        plain = binascii.hexlify("".rjust(32, '\x00'))
        cipher, nonce = remote.privee.encrypt(plain, remote.pubber.key)
        body = raeting.HELLO_PACKER.pack(plain, remote.privee.pubraw, cipher, nonce)

        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.hello,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove()
            return
        self.transmit(packet)
        console.concise("Allower Do Hello at {0}\n".format(self.stack.store.stamp))

    def cookie(self):
        '''
        Process cookie packet
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        if not isinstance(body, basestring):
            emsg = "Invalid format of cookie packet body"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_cookie')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        if len(body) != raeting.COOKIE_PACKER.size:
            emsg = "Invalid length of cookie packet body"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_cookie')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        cipher, nonce = raeting.COOKIE_PACKER.unpack(body)

        remote = self.stack.estates[self.reid]

        msg = remote.privee.decrypt(cipher, nonce, remote.pubber.key)
        if len(msg) != raeting.COOKIESTUFF_PACKER.size:
            emsg = "Invalid length of cookie stuff"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_cookie')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        shortraw, seid, deid, oreo = raeting.COOKIESTUFF_PACKER.unpack(msg)

        if seid != remote.eid or deid != self.stack.estate.eid:
            emsg = "Invalid seid or deid fields in cookie stuff"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_cookie')
            self.remove()
            return
            #raeting.TransactionError(emsg)

        self.oreo = binascii.hexlify(oreo)
        remote.publee = nacling.Publican(key=shortraw)

        self.initiate()

    def initiate(self):
        '''
        Send initiate request to cookie response to hello request
        '''
        if self.reid not in self.stack.estates:
            emsg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_remote_eid')
            self.remove()
            return

        remote = self.stack.estates[self.reid]

        vcipher, vnonce = self.stack.estate.priver.encrypt(remote.privee.pubraw,
                                                remote.pubber.key)

        fqdn = remote.fqdn.ljust(128, ' ')

        stuff = raeting.INITIATESTUFF_PACKER.pack(self.stack.estate.priver.pubraw,
                                                  vcipher,
                                                  vnonce,
                                                  fqdn)

        cipher, nonce = remote.privee.encrypt(stuff, remote.publee.key)

        oreo = binascii.unhexlify(self.oreo)
        body = raeting.INITIATE_PACKER.pack(remote.privee.pubraw,
                                            oreo,
                                            cipher,
                                            nonce)

        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.initiate,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove()
            return

        self.transmit(packet)
        console.concise("Allower Do Initiate at {0}\n".format(self.stack.store.stamp))

    def allow(self):
        '''
        Process ackInitiate packet
        Perform allowment in response to ack to initiate packet
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        self.stack.estates[self.reid].allowed = True
        self.ackFinal()
        #self.remove()

    def ackFinal(self):
        '''
        Send ack to ack Initiate to terminate transaction
        '''
        if self.reid not in self.stack.estates:
            emsg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_remote_eid')
            self.remove()
            return

        body = ""
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.ack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove()
            return

        self.transmit(packet)
        console.concise("Allower Ack Final at {0}\n".format(self.stack.store.stamp))

        self.remove()

class Allowent(Correspondent):
    '''
    RAET protocol Allowent Correspondent class Dual of Allower
    CurveCP handshake
    '''
    Timeout = 2.0
    RedoTimeoutMin = 0.25 # initial timeout
    RedoTimeoutMax = 1.0 # max timeout

    def __init__(self, redoTimeoutMin=None, redoTimeoutMax=None, **kwa):
        '''
        Setup instance
        '''
        kwa['kind'] = raeting.trnsKinds.allow
        if 'reid' not  in kwa:
            emsg = "Missing required keyword argumens: '{0}'".format('reid')
            raise TypeError(emsg)
        super(Allowent, self).__init__(**kwa)

        self.redoTimeoutMax = redoTimeoutMax or self.RedoTimeoutMax
        self.redoTimeoutMin = redoTimeoutMin or self.RedoTimeoutMin
        self.redoTimer = aiding.StoreTimer(self.stack.store,
                                           duration=self.redoTimeoutMin)

        remote = self.stack.estates[self.reid]
        if not remote.joined:
            emsg = "Must be joined first"
            console.terse(emsg + '\n')
            self.stack.incStat('unjoined_allow_attempt')
            return
            #raise raeting.TransactionError(emsg)
        #Current .sid was set by stack from rxPacket.data sid so it is the new rsid
        if not remote.validRsid(self.sid):
            emsg = "Stale sid '{0}' in packet".format(self.sid)
            console.terse(emsg + '\n')
            self.stack.incStat('stale_sid_allow_attempt')
            return
            #raise raeting.TransactionError(emsg)
        remote.rsid = self.sid #update last received rsid for estate
        remote.rtid = self.tid #update last received rtid for estate
        self.oreo = None #keep locally generated oreo around for redos
        remote.refresh() # refresh short term keys and .allowed
        self.prep() # prepare .txData
        self.add(self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Allowent, self).receive(packet) #  self.rxPacket = packet

        if packet.data['tk'] == raeting.trnsKinds.allow:
            if packet.data['pk'] == raeting.pcktKinds.hello:
                self.hello()
            elif packet.data['pk'] == raeting.pcktKinds.initiate:
                self.initiate()
            elif packet.data['pk'] == raeting.pcktKinds.ack:
                self.final()

    def process(self):
        '''
        Perform time based processing of transaction

        '''
        if self.timeout > 0.0 and self.timer.expired:
            self.nack()
            console.concise("Allowent timed out at {0}\n".format(self.stack.store.stamp))
            return

        # need to perform the check for accepted status and then send accept
        if self.redoTimer.expired:
            duration = min(
                        max(self.redoTimeoutMin,
                              self.redoTimer.duration) * 2.0,
                        self.redoTimeoutMax)
            self.redoTimer.restart(duration=duration)

            if self.txPacket:
                if self.txPacket.data['pk'] == raeting.pcktKinds.cookie:
                    self.transmit(self.txPacket) #redo
                    console.concise("Allowent Redo Cookie at {0}\n".format(self.stack.store.stamp))

                if self.txPacket.data['pk'] == raeting.pcktKinds.ack:
                    self.transmit(self.txPacket) #redo
                    console.concise("Allowent Redo Ack at {0}\n".format(self.stack.store.stamp))

    def prep(self):
        '''
        Prepare .txData
        '''
        remote = self.stack.estates[self.reid]
        self.txData.update( sh=self.stack.estate.host,
                            sp=self.stack.estate.port,
                            dh=remote.host,
                            dp=remote.port,
                            se=self.stack.estate.eid,
                            de=self.reid,
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid, )

    def hello(self):
        '''
        Process hello packet
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        if not isinstance(body, basestring):
            emsg = "Invalid format of hello packet body"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_hello')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        if len(body) != raeting.HELLO_PACKER.size:
            emsg = "Invalid length of hello packet body"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_hello')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        plain, shortraw, cipher, nonce = raeting.HELLO_PACKER.unpack(body)

        remote = self.stack.estates[self.reid]
        remote.publee = nacling.Publican(key=shortraw)
        msg = self.stack.estate.priver.decrypt(cipher, nonce, remote.publee.key)
        if msg != plain :
            emsg = "Invalid plain not match decrypted cipher"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_hello')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        self.cookie()

    def cookie(self):
        '''
        Send Cookie Packet
        '''
        if self.reid not in self.stack.estates:
            emsg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_remote_eid')
            self.remove()
            return

        remote = self.stack.estates[self.reid]
        oreo = self.stack.estate.priver.nonce()
        self.oreo = binascii.hexlify(oreo)

        stuff = raeting.COOKIESTUFF_PACKER.pack(remote.privee.pubraw,
                                                self.stack.estate.eid,
                                                remote.eid,
                                                oreo)

        cipher, nonce = self.stack.estate.priver.encrypt(stuff, remote.publee.key)
        body = raeting.COOKIE_PACKER.pack(cipher, nonce)
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.cookie,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove()
            return
        self.transmit(packet)
        console.concise("Allowent Do Cookie at {0}\n".format(self.stack.store.stamp))

    def initiate(self):
        '''
        Process initiate packet
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        if not isinstance(body, basestring):
            emsg = "Invalid format of initiate packet body"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_initiate')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        if len(body) != raeting.INITIATE_PACKER.size:
            emsg = "Invalid length of initiate packet body"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_initiate')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        shortraw, oreo, cipher, nonce = raeting.INITIATE_PACKER.unpack(body)

        remote = self.stack.estates[self.reid]

        if shortraw != remote.publee.keyraw:
            emsg = "Mismatch of short term public key in initiate packet"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_initiate')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        if (binascii.hexlify(oreo) != self.oreo):
            emsg = "Stale or invalid cookie in initiate packet"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_initiate')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        msg = remote.privee.decrypt(cipher, nonce, remote.publee.key)
        if len(msg) != raeting.INITIATESTUFF_PACKER.size:
            emsg = "Invalid length of initiate stuff"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_initiate')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        pubraw, vcipher, vnonce, fqdn = raeting.INITIATESTUFF_PACKER.unpack(msg)
        if pubraw != remote.pubber.keyraw:
            emsg = "Mismatch of long term public key in initiate stuff"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_initiate')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        fqdn = fqdn.rstrip(' ')
        if fqdn != self.stack.estate.fqdn:
            emsg = "Mismatch of fqdn in initiate stuff"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_initiate')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        vouch = self.stack.estate.priver.decrypt(vcipher, vnonce, remote.pubber.key)
        if vouch != remote.publee.keyraw or vouch != shortraw:
            emsg = "Short term key vouch failed"
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_initiate')
            self.remove()
            return
            #raise raeting.TransactionError(emsg)

        self.ackInitiate()

    def ackInitiate(self):
        '''
        Send ack to initiate request
        '''
        if self.reid not in self.stack.estates:
            msg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(msg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_remote_eid')
            self.remove()
            return

        body = ""
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.ack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove()
            return

        self.transmit(packet)
        console.concise("Allowent Do Ack at {0}\n".format(self.stack.store.stamp))

        self.allow()

    def allow(self):
        '''
        Perform allowment
        '''
        self.stack.estates[self.reid].allowed = True

    def final(self):
        '''
        Process ackFinal packet
        '''
        if not self.stack.parseInner(self.rxPacket):
            return
        self.remove()

    def nack(self):
        '''
        Send nack to terminate allower transaction
        '''
        if self.reid not in self.stack.estates:
            emsg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_remote_eid')
            self.remove()
            return

        body = odict()
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.nack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove()
            return

        self.transmit(packet)
        self.remove()
        console.concise("Allowent Reject at {0}\n".format(self.stack.store.stamp))

class Messenger(Initiator):
    '''
    RAET protocol Messenger Initiator class Dual of Messengent
    Generic messages
    '''
    def __init__(self, **kwa):
        '''
        Setup instance
        '''
        kwa['kind'] = raeting.trnsKinds.message
        super(Messenger, self).__init__(**kwa)
        self.segmentage = None # special packet to hold segments if any
        if self.reid is None:
            self.reid = self.stack.estates.values()[0].eid # zeroth is channel master
        remote = self.stack.estates[self.reid]
        if not remote.allowed:
            emsg = "Must be allowed first"
            console.terse(emsg + '\n')
            self.stack.incStat('unallowed_message_attempt')
            return
            #raise raeting.TransactionError(emsg)
        self.sid = remote.sid
        self.tid = remote.nextTid()
        self.prep() # prepare .txData
        self.add(self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Messenger, self).receive(packet)

        if packet.data['tk'] == raeting.trnsKinds.message:
            if packet.data['pk'] == raeting.pcktKinds.ack:
                self.done()

    def prep(self):
        '''
        Prepare .txData
        '''
        remote = self.stack.estates[self.reid]
        self.txData.update( sh=self.stack.estate.host,
                            sp=self.stack.estate.port,
                            dh=remote.host,
                            dp=remote.port,
                            se=self.stack.estate.eid,
                            de=self.reid,
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid,)

    def message(self, body=None):
        '''
        Send message
        '''
        if self.reid not in self.stack.estates:
            emsg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(emsg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_remote_eid')
            self.remove()
            return

        if body is None:
            body = odict()

        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.message,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove()
            return
        if packet.segmented:
            self.segmentage = packet
            for segment in self.segmentage.segments.values():
                self.transmit(segment)
        else:
            self.transmit(packet)

    def done(self):
        '''
        Complete transaction and remove
        '''
        self.remove()

class Messengent(Correspondent):
    '''
    RAET protocol Messengent Correspondent class Dual of Messenger
    Generic Messages
    '''
    def __init__(self, **kwa):
        '''
        Setup instance
        '''
        kwa['kind'] = raeting.trnsKinds.message
        if 'reid' not  in kwa:
            emsg = "Missing required keyword argumens: '{0}'".format('reid')
            raise TypeError(emsg)
        super(Messengent, self).__init__(**kwa)
        self.segmentage = None # special packet to hold segments if any
        remote = self.stack.estates[self.reid]
        if not remote.allowed:
            emsg = "Must be allowed first"
            console.terse(emsg + '\n')
            self.stack.incStat('unallowed_message_attempt')
            return
            #raise raeting.TransactionError(emsg)
        #Current .sid was set by stack from rxPacket.data sid so it is the new rsid
        if not remote.validRsid(self.sid):
            emsg = "Stale sid '{0}' in packet".format(self.sid)
            console.terse(emsg + '\n')
            self.stack.incStat('stale_sid_message_attempt')
            return
            #raise raeting.TransactionError(emsg)
        remote.rsid = self.sid #update last received rsid for estate
        remote.rtid = self.tid #update last received rtid for estate
        self.prep() # prepare .txData
        self.add(self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Messengent, self).receive(packet)

        # resent message
        if packet.data['tk'] == raeting.trnsKinds.message:
            if packet.data['pk'] == raeting.pcktKinds.message:
                self.message()

    def prep(self):
        '''
        Prepare .txData
        '''
        remote = self.stack.estates[self.reid]
        self.txData.update( sh=self.stack.estate.host,
                            sp=self.stack.estate.port,
                            dh=remote.host,
                            dp=remote.port,
                            se=self.stack.estate.eid,
                            de=self.reid,
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid,)

    def message(self):
        '''
        Process message packet
        '''
        console.verbose("segment count = {0} tid={1}\n".format(
                 self.rxPacket.data['sc'], self.tid))
        if self.rxPacket.segmentive:
            if not self.segmentage:
                self.segmentage = packeting.RxPacket(stack=self.stack,
                                                data=self.rxPacket.data)
            self.segmentage.parseSegment(self.rxPacket)
            if not self.segmentage.desegmentable():
                return
            self.segmentage.desegmentize()
            if not self.stack.parseInner(self.segmentage):
                return
            body = self.segmentage.body.data
        else:
            if not self.stack.parseInner(self.rxPacket):
                return
            body = self.rxPacket.body.data

        self.stack.rxMsgs.append(body)
        self.ackMessage()

    def ackMessage(self):
        '''
        Send ack to message
        '''
        if self.reid not in self.stack.estates:
            msg = "Invalid remote destination estate id '{0}'".format(self.reid)
            #raise raeting.TransactionError(msg)
            console.terse(emsg + '\n')
            self.stack.incStat('invalid_remote_eid')
            self.remove()
            return

        body = odict()
        packet = packeting.TxPacket(stack=self.stack,
                                    kind=raeting.pcktKinds.ack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except raeting.PacketError as ex:
            console.terse(ex + '\n')
            self.stack.incStat("packing_error")
            self.remove()
            return
        self.transmit(packet)
        self.remove()

