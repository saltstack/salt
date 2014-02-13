# -*- coding: utf-8 -*-
'''
stacking.py raet protocol stacking classes
'''
# pylint: disable=W0611

# Import python libs
import socket
from collections import deque, namedtuple, Mapping
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
        self.device = device or LocalDevice(stack=self, did=did, ha=ha)
        self.transactions = odict() #transactions
        self.rxdsUdp = deque()
        self.txdsUdp = deque()
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
            raise raeting.RaetError(msg)
        device.stack = self
        self.devices[did] = device

    def moveRemoteDevice(self, odid, ndid):
        '''
        Move device at odid to ndid
        '''
        if ndid in self.devices:
            msg = "Cannot move, '{0}' already exists".format(ndid)
            raise raeting.RaetError(msg)

        if odid not in self.devices:
            msg = "Cannot move '{0}' does not exist".format(odid)
            raise raeting.RaetError(msg)

        device = self.devices[odid]
        del self.devices[odid]
        device.did = ndid
        self.devices.insert(0, device.did, device)

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
                self.rxdsUdp.append((rx, ra, self.serverUdp.ha))

            while self.txdsUdp:
                tx, ta = self.txdsUdp.popleft()  # duple = (packet, destination address)
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
            raise raeting.RaetError(msg)
        self.txdsUdp.append((packed, self.devices[ddid].ha))

    def fetchParseRxUdp(self):
        '''
        Fetch from UDP deque next packet tuple
        Parse packet
        Return packet if verified and destination did matches
        Otherwise return None
        '''
        try:
            raw, ra, da = self.rxdsUdp.popleft()
        except IndexError:
            return None

        print "{0} received\n{1}".format(self.name, raw)

        packet = packeting.RxPacket(packed=raw)
        if not packet.parseOuter():
            return None

        ddid = packet.data['dd']
        if ddid != 0 and self.device.did != 0 and ddid != self.device.did:
            return None

        sh, sp = ra
        dh, dp = da
        packet.data.update(sh=sh, sp=sp, dh=dh, dp=dp)

        if not packet.parseInner():
            return None

        return packet

    def processRxUdp(self):
        '''
        Retrieve next packet from stack receive queue if any and parse
        Process associated transaction or reply with new corresponder transaction
        '''
        packet = self.fetchParseRxUdp()
        if not packet:
            return

        print "{0} received\n{1}".format(self.name, packet.data)
        print "{0} received\n{1}".format(self.name, packet.body.data)
        print "{0} received packet index = '{1}'".format(self.name, packet.index)

        trans = self.transactions.get(packet.index, None)
        if trans:
            trans.receive(packet)
            return

        if packet.data['cf']: #corresponder to stale transaction so drop
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
            self.replyJoin(packet) # create new joinee transaction

    def join(self):
        '''
        Initiate join transaction
        '''
        data = odict(hk=self.Hk, bk=self.Bk)
        joiner = Joiner(stack=self, sid=0, txData=data)
        joiner.join()

    def replyJoin(self, packet):
        '''
        Correspond with joinee transaction to received join packet
        '''
        data = odict(hk=self.Hk, bk=self.Bk)
        joinee = Joinee(stack=self,
                        sid=packet.data['si'],
                        tid=packet.data['ti'],
                        txData=data, rxPacket=packet)
        joinee.pend()
        self.devices[joinee.rdid].accepted = True
        joinee.accept()


class Device(object):
    '''
    RAET protocol endpoint device object
    '''
    Did = 2 # class attribute

    def __init__(self, stack=None, did=None, sid=0, tid=0,
                 host="", port=raeting.RAET_PORT, ha=None, ):
        '''
        Setup Device instance
        '''
        self.stack = stack  # Stack object that manages this device
        if did is None:
            if self.stack:
                while Device.Did in self.stack.devices:
                    Device.Did += 1
                did = Device.Did
            else:
                did = 0
        self.did = did # device ID

        self.accepted = None
        self.allowed = None

        self.sid = sid # current session ID
        self.tid = tid # current transaction ID

        if ha:  # takes precendence
            host, port = ha
        self.host = socket.gethostbyname(host)
        self.port = port

    @property
    def ha(self):
        '''
        property that returns ip address (host, port) tuple
        '''
        return (self.host, self.port)

    @ha.setter
    def ha(self, ha):
        self.host, self.port = ha

    def nextSid(self):
        '''
        Generates next session id number.
        '''
        self.sid += 1
        if self.sid > 0xffffffffL:
            self.sid = 1  # rollover to 1
        return self.sid

    def nextTid(self):
        '''
        Generates next session id number.
        '''
        self.tid += 1
        if self.tid > 0xffffffffL:
            self.tid = 1  # rollover to 1
        return self.tid

class LocalDevice(Device):
    '''
    RAET protocol endpoint local device object
    Maintains signer for signing and privateer for encrypt/decript
    '''
    def __init__(self, signkey=None, prikey=None, **kwa):
        '''
        Setup Device instance

        signkey is either nacl SigningKey or hex encoded key
        prikey is either nacl PrivateKey or hex encoded key
        '''
        super(LocalDevice, self).__init__(**kwa)
        self.signer = nacling.Signer(signkey)
        self.priver = nacling.Privateer(prikey) # Long term key


class RemoteDevice(Device):
    '''
    RAET protocol endpoint remote device object
    Maintains verifier for verifying signatures and publican for encrypt/decript
    '''
    def __init__(self, verikey=None, pubkey=None, rsid=0, rtid=0, **kwa):
        '''
        Setup Device instance

        verikey is either nacl VerifyKey or hex encoded key
        pubkey is either nacl PublicKey or hex encoded key
        '''
        if 'host' not in kwa and 'ha' not in kwa:
            kwa['ha'] = ('127.0.0.1', raeting.RAET_TEST_PORT)
        super(RemoteDevice, self).__init__(**kwa)
        self.verfer = nacling.Verifier(verikey)
        self.pubber = nacling.Publican(pubkey) #long term key
        self.publee = nacling.Publican() # short term key
        self.privee = nacling.Privateer() # short term key

        self.rsid = rsid # last sid received from remote when CrdrFlag is True
        self.rtid = rtid # last tid received from remote when CrdrFlag is True


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
                master = RemoteDevice(did=0, ha=('127.0.0.1', raeting.RAET_PORT))
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
        packet.pack()
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

        device = RemoteDevice(stack=self.stack,
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
        packet.pack()
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
        packet.pack()
        self.transmit(packet)
        del self.stack.transactions[self.rxPacket.index]

