# -*- coding: utf-8 -*-
'''
devicing.py raet protocol device classes
'''
# pylint: skip-file
# pylint: disable=W0611
# Import python libs
import socket

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base import aiding

from . import raeting
from . import nacling

from ioflo.base.consoling import getConsole
console = getConsole()

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

        self.sid = sid # current session ID
        self.tid = tid # current transaction ID

        if ha:  # takes precendence
            host, port = ha
        self.host = socket.gethostbyname(host)
        self.port = port
        self.fqdn = socket.getfqdn(self.host)

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

    def validSid(self, sid):
        '''
        Compare new sid to old .sid and return True if new is greater than old
        modulo N where N is 2^32 = 0x100000000
        And greater means the difference is less than N/2
        '''
        return (((sid - self.sid) % 0x100000000) < (0x100000000 / 2))

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
        self.joined = None
        self.allowed = None
        self.privee = nacling.Privateer() # short term key manager
        self.publee = nacling.Publican() # correspondent short term key  manager
        self.verfer = nacling.Verifier(verikey) # correspondent verify key manager
        self.pubber = nacling.Publican(pubkey) # correspondent long term key manager

        self.rsid = rsid # last sid received from remote when RmtFlag is True
        self.rtid = rtid # last tid received from remote when RmtFlag is True

    def refresh(self):
        '''
        Refresh short term keys
        '''
        self.allowed = None
        self.privee = nacling.Privateer() # short term key
        self.publee = nacling.Publican() # correspondent short term key  manager

    def validRsid(self, rsid):
        '''
        Compare new rsid to old .rsid and return True if new is greater than old
        modulo N where N is 2^32 = 0x100000000
        And greater means the difference is less than N/2
        '''
        return (((rsid - self.rsid) % 0x100000000) < (0x100000000 / 2))
