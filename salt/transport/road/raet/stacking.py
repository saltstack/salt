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


class Stack(object):
    '''
    RAET protocol stack object
    '''
    def __init__(    self,
                     version=raeting.VERSION,
                     device=None,
                     did=None,
                     ha=("", raeting.RAET_PORT)):
        '''
        Setup Stack instance
        '''
        self.version = version
         # local device for this stack
        self.device = device or Device(stack=self, did=did, ha=ha)
        # remote devices attached to this stack
        self.devices = odict()
        self.transactions = odict() #transactions

        self.rxdsUdp = deque()
        self.txdsUdp = deque()
        self.serverUdp = aiding.SocketUdpNb(ha=self.device.ha)
        self.serverUdp.reopen()  # open socket
        self.device.ha = self.serverUdp.ha # update device host address after open

    def addRemoteDevice(self, device, did=None):
        '''
        Add a remote device to .devices
        '''
        if did is None:
            did = device.did

        if did == 0:
            msg = "Forbidden to add device with id '{0}'".format(did)
            raise raeting.RaetError(msg)

        if did in self.devices:
            msg = "Device with id '{0}' alreadys exists".format(did)
            raise raeting.RaetError(msg)
        device.stack = self
        self.devices[did] = device

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

    def processRxUdp(self):
        '''
        Retrieve next packet from stack receive queue if any and process
        Return packet if verified and destination did matches
        Otherwise return None
        '''
        try:
            raw, ra, da = self.rxdsUdp.popleft()
        except IndexError:
            return None

        packet = packeting.RxPacket(packed=raw)
        if not packet.parseFore():
            return None

        ddid = packet.data['dd']
        if ddid != 0 and ddid != self.device.did:
            return None

        sh, sp = ra
        dh, dp = da
        packet.data.update(sh=sh, sp=sp, dh=dh, dp=dp )

        if not packet.parseBack():
           return None

        return packet


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


class Device(object):
    '''
    RAET protocol endpoint device object
    '''
    Did = 1 # class attribute

    def __init__(   self, stack=None, did=None, sid=0, tid=0,
                    host="", port=raeting.RAET_PORT, ha=None, ):
        '''
        Setup Device instance
        '''
        self.stack = stack # Stack object that manages this device
        if did is None:
            did = Device.Did
            Device.Did += 1
        self.did = did # device ID

        self.sid = sid # current session ID
        self.tid = tid # current transaction ID

        if ha: #takes precendence
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
        if (self.sid > 0xffffffffL):
            self.sid = 1 # rollover to 1
        return self.sid

    def nextTid(self):
        '''
        Generates next session id number.
        '''
        self.tid += 1
        if (self.tid > 0xffffffffL):
            self.tid = 1 # rollover to 1
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
        self.privateer = nacling.Privateer(key)

class RemoteDevice(Device):
    '''
    RAET protocol endpoint remote device object
    Maintains verifier for verifying signatures and publican for encrypt/decript
    '''
    def __init__(self, verikey=None, pubkey=None, **kwa):
        '''
        Setup Device instance

        verikey is either nacl VerifyKey or hex encoded key
        pubkey is either nacl PublicKey or hex encoded key
        '''
        if 'host' not in kwa and 'ha' not in kwa:
            kwa['ha'] = ('127.0.0.1', raeting.RAET_TEST_PORT)
        super(RemoteDevice, self).__init__(**kwa)
        self.verifier = nacling.Verifier(verikey)
        self.publican = nacling.Publican(pubkey)

class Transaction(object):
    '''
    RAET protocol transaction class
    '''
    def __init__(self, stack=None, kind=None, rdid=None,
                 crdr=False, bcst=False, sid=None, tid=None,
                 rxData=None, txData=None,):
        '''
        Setup Transaction instance
        '''
        self.stack = stack
        self.kind = kind or raeting.PACKET_DEFAULTS['sk']

        # local device is the .stack.device
        self.rdid = rdid # remote device did

        self.crdr = crdr
        self.bcst = bcst

        self.sid = sid
        self.tid = tid

        self.rxData = rxData or odict()
        self.txData = txData or odict()
        self.rxPacket = None # last rx packet
        self.txPacket = None # last tx packet

    def transmit(self, packet):
        '''
        Queue tx duple on stack transmit queue
        '''
        self.stack.txUdp(packet.packed, self.rdid)
        self.txPacket = packet

    def start(self):
        '''
        Build first packet
        '''
        return None

class Initiator(Transaction):
    '''
    RAET protocol initiator transaction class
    '''
    def __init__(self, crdr=False, **kwa):
        '''
        Setup Transaction instance
        '''
        crdr = False # force crdr to False
        super(Initiator, self).__init__(crdr=crdr, **kwa)
        if self.sid is None: # use current session id of local device
            self.sid = self.stack.device.sid
        if self.tid is None: # use next tid
            self.tid = self.stack.device.nextTid()

class Corresponder(Transaction):
    '''
    RAET protocol corresponder transaction class
    '''
    def __init__(self, crdr=True, **kwa):
        '''
        Setup Transaction instance
        '''
        crdr = True # force crdr to True
        super(Corresponder, self).__init__(crdr=crdr, **kwa)

class Joiner(Initiator):
    '''
    RAET protocol Joiner transaction class
    '''
    def __init__(self, rdid=None,  **kwa):
        '''
        Setup Transaction instance
        '''
        if rdid is None:
            rdid = self.stack.devices.values()[0].did # zeroth is channel master
        super(Joiner, self).__init__(rdid=rdid, **kwa)

    def start(self, body=None):
        '''
        Build first packet
        '''
        body = body or odict()
        if self.rdid not in self.stack.devices:
            msg = "Invalid remote destination device id '{0}'".format(self.rdid)
            raise raeting.RaetError(msg)
        self.txData.update(sh=self.stack.device.host,
                           sp=self.stack.device.port,
                           dh=self.stack.devices[self.rdid].host,
                           dp=self.stack.devices[self.rdid].port, )
        self.txData.update(sd=self.stack.device.did, dd=self.rdid, sk=self.kind,
                         cf=self.crdr, bf=self.bcst,
                         si=self.sid, ti=self.tid, nk=1, tk=1)
        body.update(msg='Hello Raet World', extra='what is this')
        packet = packeting.TxPacket(embody=body, data=self.txData)
        packet.pack()
        self.transmit(packet)
        return None
