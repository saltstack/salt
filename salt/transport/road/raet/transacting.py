# -*- coding: utf-8 -*-
'''
stacking.py raet protocol stacking classes
'''
# pylint: disable=W0611

# Import python libs
import socket

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base import aiding

from . import raeting
from . import nacling
from . import packeting
from . import devicing

from ioflo.base.consoling import getConsole
console = getConsole()


class Transaction(object):
    '''
    RAET protocol transaction class
    '''
    Timeout =  5.0 # default timeout

    def __init__(self, stack=None, kind=None, timeout=None, start=None,
                 rdid=None, rmt=False, bcst=False, sid=None, tid=None,
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
        self.timer = aiding.Timer(duration=self.timeout)
        if start: #enables synchronized starts not just current time
            self.timer.restart(start=start)

        # local device is the .stack.device
        self.rdid = rdid  # remote device did

        self.rmt = rmt
        self.bcst = bcst

        self.sid = sid
        self.tid = tid

        self.txData = txData or odict() # data used to prepare last txPacket
        self.txPacket = txPacket  # last tx packet
        self.rxPacket = rxPacket  # last rx packet

    @property
    def index(self):
        '''
        Property is transaction tuple (rf, ld, rd, si, ti, bf,)
        '''
        return ((self.rmt, self.stack.device.did, self.rdid, self.sid, self.tid, self.bcst,))

    def process(self):
        '''
        Process time based handling of transaction like timeout or retries
        '''
        pass

    def receive(self, packet):
        '''
        Process received packet
        '''
        self.rxPacket = packet

    def transmit(self, packet):
        '''
        Queue tx duple on stack transmit queue
        '''
        self.stack.txUdp(packet.packed, self.rdid)
        self.txPacket = packet

    def remove(self, index=None):
        '''
        Remove self from stack transactions
        '''
        if not index:
            index = self.index
        self.stack.removeTransaction(index, transaction=self)

    def signature(self, msg):
        '''
        Return signature resulting from signing msg
        '''
        return (self.stack.device.signer.signature(msg))

    def verify(self, signature, msg):
        '''
        Return result of verifying msg with signature
        '''
        return (self.stack.devices[self.rid].verfer.verify(signature, msg))

    def encrypt(self, msg):
        '''
        Return (cipher, nonce) duple resulting from encrypting message
        with short term keys
        '''
        remote = self.stack.devices[self.rid]
        return (self.stack.device.privee.encrypt(msg, remote.publee.key))

    def decrypt(self, cipher, nonce):
        '''
        Return msg resulting from decrypting cipher and nonce
        with short term keys
        '''
        remote = remote = self.stack.devices[self.rid]
        return (self.stack.device.privee.decrypt(cipher, nonce, remote.publee, key))

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
        if self.sid is None:  # use current session id of local device
            self.sid = self.stack.device.sid
        if self.tid is None:  # use next tid
            self.tid = self.stack.device.nextTid()

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
            msg = "Missing required keyword arguments: '{0}'".format(missing)
            raise TypeError(msg)

        super(Correspondent, self).__init__(**kwa)

class Joiner(Initiator):
    '''
    RAET protocol Joiner Initiator class Dual of Joinent
    '''
    def __init__(self, **kwa):
        '''
        Setup Transaction instance
        '''
        kwa['kind'] = raeting.trnsKinds.join
        super(Joiner, self).__init__(**kwa)
        if self.rdid is None:
            if not self.stack.devices: # no channel master so make one
                master = devicing.RemoteDevice(did=0, ha=('127.0.0.1', raeting.RAET_PORT))
                self.stack.addRemoteDevice(master)

            self.rdid = self.stack.devices.values()[0].did # zeroth is channel master
        self.stack.transactions[self.index] = self
        print "Added {0} transaction to {1} at '{2}'".format(
                self.__class__.__name__, self.stack.name, self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Joiner, self).receive(packet)

        if packet.data['tk'] == raeting.trnsKinds.join:
            if packet.data['pk'] == raeting.pcktKinds.ack:
                self.pend()

            elif packet.data['pk'] == raeting.pcktKinds.response:
                self.accept()

    def join(self, body=None):
        '''
        Send join request
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            msg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(msg)

        self.txData.update( sh=self.stack.device.host,
                            sp=self.stack.device.port,
                            dh=self.stack.devices[self.rdid].host,
                            dp=self.stack.devices[self.rdid].port,
                            sd=self.stack.device.did,
                            dd=self.rdid,
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid,
                            ck=raeting.coatKinds.nada,
                            fk=raeting.footKinds.nada)
        body.update(verhex=self.stack.device.signer.verhex,
                    pubhex=self.stack.device.priver.pubhex)
        packet = packeting.TxPacket(transaction=self,
                                    kind=raeting.pcktKinds.request,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except packeting.PacketError as ex:
            print ex
            self.remove()
            return
        self.transmit(packet)

    def accept(self):
        '''
        Perform acceptance
        '''
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        ldid = body.get('ldid')
        if not ldid:
            msg = "Missing local device id in accept packet"
            raise raeting.TransactionError(msg)

        rdid = body.get('rdid')
        if not rdid:
            msg = "Missing remote device id in accept packet"
            raise raeting.TransactionError(msg)

        verhex = body.get('verhex')
        if not verhex:
            msg = "Missing remote verifier key in accept packet"
            raise raeting.TransactionError(msg)

        pubhex = body.get('pubhex')
        if not pubhex:
            msg = "Missing remote crypt key in accept packet"
            raise raeting.TransactionError(msg)

        index = self.index # save before we change it

        self.stack.device.did = ldid
        remote = self.stack.devices[self.rdid]
        remote.verfer = nacling.Verifier(key=verhex)
        remote.pubber = nacling.Publican(key=pubhex)
        if remote.did != rdid: #move remote device to new index
            self.stack.moveRemoteDevice(remote.did, rdid)
        #self.stack.device.accepted = True
        remote.accepted = True
        self.remove(index)

    def pend(self):
        '''
        Perform pend as a result of accept ack reception
        '''
        #set timer for redo
        pass


class Joinent(Correspondent):
    '''
    RAET protocol Joinent transaction class, dual of Joiner
    '''
    def __init__(self, **kwa):
        '''
        Setup Transaction instance
        '''
        kwa['kind'] = raeting.trnsKinds.join
        super(Joinent, self).__init__(**kwa)
        # Since corresponding bootstrap transaction use packet.index not self.index
        self.stack.transactions[self.rxPacket.index] = self
        print "Added {0} transaction to {1} at '{2}'".format(
                self.__class__.__name__, self.stack.name, self.rxPacket.index)

    def pend(self):
        '''
        Perform pend operation of pending device being accepted onto channel
        '''
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        # need to add search for existing device with same host,port address

        device = devicing.RemoteDevice(stack=self.stack,
                              host=data['sh'],
                              port=data['sp'],
                              rsid=self.sid,
                              rtid=self.tid, )
        self.stack.addRemoteDevice(device) #provisionally add .accepted is None

        self.rdid = device.did

        verhex = body.get('verhex')
        if not verhex:
            msg = "Missing remote verifier key in join packet"
            raise raeting.TransactionError(msg)

        pubhex = body.get('pubhex')
        if not pubhex:
            msg = "Missing remote crypt key in join packet"
            raise raeting.TransactionError(msg)

        device.verfer = nacling.Verifier(key=verhex)
        device.pubber = nacling.Publican(key=pubhex)

        self.ackJoin()

    def ackJoin(self, body=None):
        '''
        Send ack to join request
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            msg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(msg)

        #since bootstrap transaction use the reversed sdid and ddid from packet
        self.txData.update( sh=self.stack.device.host,
                            sp=self.stack.device.port,
                            dh=self.stack.devices[self.rdid].host,
                            dp=self.stack.devices[self.rdid].port,
                            sd=self.rxPacket.data['dd'],
                            dd=self.rxPacket.data['sd'],
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid,
                            ck=raeting.coatKinds.nada,
                            fk=raeting.footKinds.nada,)
        body.update()
        packet = packeting.TxPacket(transaction=self,
                                    kind=raeting.pcktKinds.ack,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except packeting.PacketError as ex:
            print ex
            self.remove(self.rxPacket.index)
            return

        self.transmit(packet)

    def accept(self, body=None):
        '''
        Send accept response to join request
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            msg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(msg)
        #since bootstrap transaction use the reversed sdid and ddid from packet
        self.txData.update( sh=self.stack.device.host,
                            sp=self.stack.device.port,
                            dh=self.stack.devices[self.rdid].host,
                            dp=self.stack.devices[self.rdid].port,
                            sd=self.rxPacket.data['dd'],
                            dd=self.rxPacket.data['sd'],
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid,
                            ck=raeting.coatKinds.nada,
                            fk=raeting.footKinds.nada,)
        body.update( ldid=self.rdid,
                     rdid=self.stack.device.did,
                     verhex=self.stack.device.signer.verhex,
                     pubhex=self.stack.device.priver.pubhex,)
        packet = packeting.TxPacket(transaction=self,
                                    kind=raeting.pcktKinds.response,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except packeting.PacketError as ex:
            print ex
            self.remove(self.rxPacket.index)
            return
        self.transmit(packet)
        self.remove(self.rxPacket.index)

class Endower(Initiator):
    '''
    RAET protocol Endower Initiator class Dual of Endowent
    CurveCP handshake
    '''
    def __init__(self, **kwa):
        '''
        Setup instance
        '''
        kwa['kind'] = raeting.trnsKinds.endow
        super(Endower, self).__init__(**kwa)
        self.oreo = None # cookie from correspondent needed until handshake completed
        if self.rdid is None:
            self.rdid = self.stack.devices.values()[0].did # zeroth is channel master
        remote = self.stack.devices[self.rdid]
        if not remote.accepted:
            emsg = "Must be accepted first"
            raise raeting.TransactionError(emsg)
        remote.refresh() # refresh short term keys
        self.stack.transactions[self.index] = self
        print "Added {0} transaction to {1} at '{2}'".format(
                self.__class__.__name__, self.stack.name, self.index)

    def receive(self, packet):
        """
        Process received packet belonging to this transaction
        """
        super(Endower, self).receive(packet)

        if packet.data['tk'] == raeting.trnsKinds.endow:
            if packet.data['pk'] == raeting.pcktKinds.cookie:
                self.initiate()

            elif packet.data['pk'] == raeting.pcktKinds.ack:
                self.endow()

    def hello(self, body=None):
        '''
        Send hello request
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            msg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(msg)

        remote = self.stack.devices[self.rid]
        self.txData.update( sh=self.stack.device.host,
                            sp=self.stack.device.port,
                            dh=remote.host,
                            dp=remote.port,
                            sd=self.stack.device.did,
                            dd=self.rdid,
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid,
                            ck=raeting.coatKinds.nada,
                            fk=raeting.footKinds.nacl)

        msg = "".rjust(64, '\x00'),
        cypher, nonce = remote.privlee.encrypt(msg, remote.pubber.key)
        body.update(plain=msg,
                    shorthex=remote.privee.pubhex,
                    cypher=cypher,
                    nonce=nonce)
        packet = packeting.TxPacket(transaction=self,
                                    kind=raeting.pcktKinds.hello,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except packeting.PacketError as ex:
            print ex
            self.remove()
            return
        self.transmit(packet)

    def cookie(self):
        '''
        Process cookie packet
        '''
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        cipher = body.get('cipher')
        if not cipher:
            msg = "Missing cipher in cookie packet"
            raise raeting.TransactionError(msg)

        nonce = body.get('nonce')
        if not nonce:
            msg = "Missing nonce in cookie packet"
            raise raeting.TransactionError(msg)

        remote = self.stack.devices[self.rdid]
        #remote.verfer = nacling.Verifier(key=verhex)
        #remote.pubber = nacling.Publican(key=pubhex)

        #self.stack.device.accepted = True

    def initiate(self, body=None):
        '''
        Send initiate request to cookie response to hello request
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            msg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.TransactionError(msg)

        remote = self.stack.devices[self.rid]
        self.txData.update( sh=self.stack.device.host,
                            sp=self.stack.device.port,
                            dh=remote.host,
                            dp=remote.port,
                            sd=self.stack.device.did,
                            dd=self.rdid,
                            tk=self.kind,
                            cf=self.rmt,
                            bf=self.bcst,
                            si=self.sid,
                            ti=self.tid,
                            ck=raeting.coatKinds.nada,
                            fk=raeting.footKinds.nacl,)

        fqdn = remote.fqdn
        body.update(shorthex=remote.privee.pubhex,
                    cookie=self.oreo,
                    )
        packet = packeting.TxPacket(transaction=self,
                                    kind=raeting.pcktKinds.initiate,
                                    embody=body,
                                    data=self.txData)
        try:
            packet.pack()
        except packeting.PacketError as ex:
            print ex
            self.remove()
            return

        self.transmit(packet)

    def endow(self):
        '''
        Perform endowment
        '''
        data = self.rxPacket.data
        body = self.rxPacket.body.data

        self.stack.devices[self.rid].endowed = True
        self.remove()