# -*- coding: utf-8 -*-
'''
estating.py raet protocol estate classes
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

class Estate(object):
    '''
    RAET protocol endpoint estate object
    '''
    Did = 2 # class attribute

    def __init__(self, stack=None, eid=None, name="", sid=0, tid=0,
                 host="", port=raeting.RAET_PORT, ha=None, ):
        '''
        Setup Estate instance
        '''
        self.stack = stack  # Stack object that manages this estate
        if eid is None:
            if self.stack:
                while Estate.Did in self.stack.estates:
                    Estate.Did += 1
                eid = Estate.Did
            else:
                eid = 0
        self.eid = eid # estate ID
        self.name = name or "estate{0}".format(self.eid)

        self.sid = sid # current session ID
        self.tid = tid # current transaction ID

        if ha:  # takes precendence
            host, port = ha
        self.host = socket.gethostbyname(host)
        self.port = port
        if self.host == '0.0.0.0':
            host = '127.0.0.1'
        else:
            host = self.host
        self.fqdn = socket.getfqdn(host)


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

class LocalEstate(Estate):
    '''
    RAET protocol endpoint local estate object
    Maintains signer for signing and privateer for encrypt/decript
    '''
    def __init__(self, main=False, sigkey=None, prikey=None, **kwa):
        '''
        Setup Estate instance

        sigkey is either nacl SigningKey or hex encoded key
        prikey is either nacl PrivateKey or hex encoded key
        '''
        super(LocalEstate, self).__init__(**kwa)
        self.main = True if main else False # main estate for road
        self.signer = nacling.Signer(sigkey)
        self.priver = nacling.Privateer(prikey) # Long term key


class RemoteEstate(Estate):
    '''
    RAET protocol endpoint remote estate object
    Maintains verifier for verifying signatures and publican for encrypt/decript
    '''
    def __init__(self, verkey=None, pubkey=None, rsid=0, rtid=0, **kwa):
        '''
        Setup Estate instance

        verkey is either nacl VerifyKey or raw or hex encoded key
        pubkey is either nacl PublicKey or raw or hex encoded key
        '''
        if 'host' not in kwa and 'ha' not in kwa:
            kwa['ha'] = ('127.0.0.1', raeting.RAET_TEST_PORT)
        super(RemoteEstate, self).__init__(**kwa)
        self.joined = None
        self.allowed = None
        self.privee = nacling.Privateer() # short term key manager
        self.publee = nacling.Publican() # correspondent short term key  manager
        self.verfer = nacling.Verifier(verkey) # correspondent verify key manager
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
