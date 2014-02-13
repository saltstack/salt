# -*- coding: utf-8 -*-
'''
stacking.py raet protocol stacking classes
'''
# pylint: disable=W0611

# Import python libs


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
    def __init__(self, stack=None, kind=None, rdid=None,
                 rmt=False, bcst=False, sid=None, tid=None,
                 txData=None, txPacket=None, rxPacket=None):
        '''
        Setup Transaction instance
        '''
        self.stack = stack
        self.kind = kind or raeting.PACKET_DEFAULTS['tk']

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

class Corresponder(Transaction):
    '''
    RAET protocol corresponder transaction class
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

        super(Corresponder, self).__init__(**kwa)


class Joiner(Initiator):
    '''
    RAET protocol Joiner transaction class Dual of Acceptor
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
            raise raeting.RaetError(msg)

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
            raise raeting.RaetError(msg)

        rdid = body.get('rdid')
        if not rdid:
            msg = "Missing remote device id in accept packet"
            raise raeting.RaetError(msg)

        verhex = body.get('verhex')
        if not verhex:
            msg = "Missing remote verifier key in accept packet"
            raise raeting.RaetError(msg)

        pubhex = body.get('pubhex')
        if not pubhex:
            msg = "Missing remote crypt key in accept packet"
            raise raeting.RaetError(msg)

        index = self.index # save before we change it

        self.stack.device.did = ldid
        device = self.stack.devices[self.rdid]
        device.verfer = nacling.Verifier(key=verhex)
        device.pubber = nacling.Publican(key=pubhex)
        if device.did != rdid: #move device to new index
            self.stack.moveRemoteDevice(device.did, rdid)
        self.stack.device.accepted = True

        del self.stack.transactions[index]


    def pend(self):
        '''
        Perform pend as a result of accept ack reception
        '''
        #set timer for retry
        pass


class Joinee(Corresponder):
    '''
    RAET protocol Joinee transaction class, Corresponder to Joiner
    '''
    def __init__(self, **kwa):
        '''
        Setup Transaction instance
        '''
        kwa['kind'] = raeting.trnsKinds.join
        super(Joinee, self).__init__(**kwa)
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
            raise raeting.RaetError(msg)

        pubhex = body.get('pubhex')
        if not pubhex:
            msg = "Missing remote crypt key in join packet"
            raise raeting.RaetError(msg)

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
            raise raeting.RaetError(msg)

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
            return

        self.transmit(packet)

    def accept(self, body=None):
        '''
        Send accept response to join request
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            msg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.RaetError(msg)
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
            return
        self.transmit(packet)
        del self.stack.transactions[self.rxPacket.index]

