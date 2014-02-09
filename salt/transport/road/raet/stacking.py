# -*- coding: utf-8 -*-
'''
stacking.py raet protocol stacking classes
'''

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

from salt.transport.table.public import pynacl

from . import raeting
from . import nacling

from ioflo.base.consoling import getConsole
console = getConsole()


class Stack(object):
    '''
    RAET protocol stack object
    '''
    def __init__(    self,
                     version=raeting.VERSION,
                     device=None, ha=("", raeting.RAET_PORT)):
        '''
        Setup Stack instance
        '''
        self.version = version
         # local device for this stack
        self.device = device or Device(stack=self, ha=ha)
        # remote devices attached to this stack
        self.devices = odict()
        self.transactions = odict() #transactions

        self.serverUdp = aiding.SocketUdpNb(ha=self.device.ha)
        self.serverUdp.reopen()  # open socket

class Device(object):
    '''
    RAET protocol endpoint device object
    '''
    Did = 0 # class attribute

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
            kwa['ha'] = ('127.0.0.1', raeting.RAET_PORT)
        super(LocalDevice, self).__init__(**kwa)
        self.verifier = nacling.Verifier(verikey)
        self.publican = nacling.Publican(pubkey)

class Transaction(object):
    '''
    RAET protocol transaction class
    '''
    def __init__(self, stack=None, kind=None, sdid=None, ddid=None,
                 crdr=None, bcst=False, sid=None, tid=None, ):
        '''
        Setup Transaction instance
        '''
        self.stack = stack
        self.kind = kind or raeting.PACKET_DEFAULTS['sk']
        self.sdid = sdid
        self.ddid = ddid
        self.crdr = crdr
        self.bcst = bcst
        self.sid = sid
        self.tid = tid

    def start(self):
        return None # next packet or None


class Initiator(Transaction):
    '''
    RAET protocol initiator transaction class
    '''
    def __init__(self, sdid=None, crdr=False,  **kwa):
        '''
        Setup Transaction instance
        '''
        if sdid is None:
            sdid = self.stack.device.did
        crdr = False # force crdr to False
        super(Initiator, self).__init__(sdid, crdr, **kwa)


class Corresponder(Transaction):
    '''
    RAET protocol corresponder transaction class
    '''
    def __init__(self, ddid=None, crdr=True, **kwa):
        '''
        Setup Transaction instance
        '''
        if ddid is None:
            ddid = self.stack.device.did
        crdr = True # force crdr to True
        super(Corresponder, self).__init__(ddid, crdr, **kwa)

class Join(Initiator):
    '''
    RAET protocol Join transaction class
    '''
    def __init__(self, ddid=None,  **kwa):
        '''
        Setup Transaction instance
        '''
        if ddid is None:
            ddid = self.stack.devices.values()[0].did # first is channel master
        super(Initiator, self).__init__(ddid, **kwa)

    def start(self)
        '''
        Build first packet
        '''
        return None