# -*- coding: utf-8 -*-
'''
behaving.py raet ioflo behaviors

See raeting.py for data format and packet field details.

Layout in DataStore


raet.udp.stack.stack
    value StackUdp
raet.udp.stack.txmsgs
    value deque()
raet.udp.stack.rxmsgs
    value deque()
raet.udp.stack.local
    name host port sigkey prikey
raet.udp.stack.status
    joined allowed idle
raet.udp.stack.destination
    value deid


'''
# pylint: skip-file
# pylint: disable=W0611

# Import Python libs
from collections import deque
try:
    import simplejson as json
except ImportError:
    import json

# Import ioflo libs
from ioflo.base.odicting import odict
from ioflo.base.globaling import *

from ioflo.base import aiding
from ioflo.base import storing
from ioflo.base import deeding

from ioflo.base.consoling import getConsole
console = getConsole()

import salt.opts

#from salt.key import RaetKey

from . import raeting, packeting, keeping, stacking, estating


class JoinerStackUdpRaetSalt(deeding.Deed):  # pylint: disable=W0232
    '''
    Initiates join transaction with master
    '''
    Ioinits = odict(
        inode=".raet.udp.stack.",
        stack='stack',
        masterhost='.salt.etc.master',
        masterport='.salt.etc.master_port', )

    def postinitio(self):
        self.mha = (self.masterhost.value, int(self.masterport.value))

    def action(self, **kwa):
        '''
        Receive any udp packets on server socket and put in rxes
        Send any packets in txes
        '''
        stack = self.stack.value
        if stack and isinstance(stack, stacking.StackUdp):
            stack.join(mha=self.mha)



#class SaltSafeKeep(keeping.SafeKeep):
    #'''
    #RAET protocol estate safe (key) data persistence and status
    #'''
    #Auto = False #auto accept

    #def __init__(self, opts=None, **kwa):
        #'''
        #Setup SaltSafeKeep instance

        #'''
        #super(SaltSafeKeep, self).__init__( **kwa)
        #if opts is None:
            #opts = salt.opts
        #self.saltRaetKey = RaetKey(opts)

    #def loadLocalData(self):
        #'''
        #Load and Return the data from the local estate
        #'''
        #keydata = self.saltRaetKey.read_local()
        #if not keydata:
            #return None
        #data = odict()

        #sigkey=safe['sighex'],
        #prikey=safe['prihex']

    #def loadAllRemoteData(self):
        #'''
        #Load and Return the data from the all the remote estate files
        #'''
        #data = odict()

        ##data[uid] = self.load(filepath)
        #return data


    #def dumpLocalEstate(self, estate):
        #'''
        #Dump the key data from the local estate
        #'''
        #data = odict([
                #('eid', estate.eid),
                #('name', estate.name),
                #('sighex', estate.signer.keyhex),
                #('prihex', estate.priver.keyhex),
                #])

        ##self.dumpLocalData(data)

        #self.saltRaetKey.write_local(estate.priver.keyhex, estate.signer.keyhex)

    #def dumpRemoteEstate(self, estate):
        #'''
        #Dump the data from the remote estate
        #'''
        #uid = estate.eid
        #data = odict([
                #('eid', estate.eid),
                #('name', estate.name),
                #('acceptance', estate.acceptance),
                #('verhex', estate.verfer.keyhex),
                #('pubhex', estate.pubber.keyhex),
                #])

        ##self.dumpRemoteData(data, uid)

    #def loadRemoteEstate(self, estate):
        #'''
        #Load and Return the data from the remote estate file
        #Override this in sub class to change uid
        #'''
        #mid = estate.eid


        #return

    #def removeRemoteEstate(self, estate):
        #'''
        #Load and Return the data from the remote estate file
        #Override this in sub class to change uid
        #'''
        #uid = estate.eid
        ##self.clearRemoteData(uid)

    #def statusRemoteEstate(self, estate, verhex=None, pubhex=None, main=True):
        #'''
        #Evaluate acceptance status of estate per its keys
        #persist key data differentially based on status
        #'''
        #data = self.loadRemoteEstate(estate)
        #status = data.get('acceptance') if data else None # pre-existing status

        #if main: #main estate logic
            #pass

        #else: #other estate logic
            #pass

        #if status != raeting.acceptances.rejected:
            #if (verhex and verhex != estate.verfer.keyhex):
                #estate.verfer = nacling.Verifier(verhex)
            #if (pubhex and pubhex != estate.pubber.keyhex):
                #estate.pubber = nacling.Publican(pubhex)
        #estate.acceptance = status
        #self.dumpRemoteEstate(estate)
        #return status

    #def rejectRemoteEstate(self, estate):
        #'''
        #Set acceptance status to rejected
        #'''
        #estate.acceptance = raeting.acceptances.rejected
        ##self.dumpRemoteEstate(estate)

    #def pendRemoteEstate(self, estate):
        #'''
        #Set acceptance status to pending
        #'''
        #estate.acceptance = raeting.acceptances.pending
        ##self.dumpRemoteEstate(estate)

    #def acceptRemoteEstate(self, estate):
        #'''
        #Set acceptance status to accepted
        #'''
        #estate.acceptance = raeting.acceptances.accepted
        ##self.dumpRemoteEstate(estate)
