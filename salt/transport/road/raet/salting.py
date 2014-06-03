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

from . import raeting, nacling, packeting, keeping, stacking, estating


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



class SaltSafe(object):
    '''
    RAET protocol estate safe (key) data persistence and status
    '''
    Auto = False #auto accept

    def __init__(self, opts=None, **kwa):
        '''
        Setup SaltSafe instance

        '''
        from salt.key import RaetKey

        if opts is None:
            opts = {}
        self.saltRaetKey = RaetKey(opts)

    def loadLocalData(self):
        '''
        Load and Return the data from the local estate
        '''
        data = self.saltRaetKey.read_local()
        if not data:
            return None
        return (odict(sighex=data['sign'], prihex=data['priv']))

    def clearLocalData(self):
        '''
        Load and Return the data from the local estate
        '''
        pass

    def loadAllRemoteData(self):
        '''
        Load and Return the data from the all the remote estate files
        '''
        data = odict()

        for status, mids in self.saltRaetKey.list_keys().items():
            for mid in mids:
                keydata = self.saltRaetKey.read_remote(mid, status)
                if keydata:
                    rdata = odict()
                    rdata['eid'] = keydata['device_id']
                    rdata['name'] = keydata['minion_id']
                    rdata['acceptance'] = raeting.ACCEPTANCES[status]
                    rdata['verhex'] = keydata['verify']
                    rdata['pubhex'] = keydata['pub']
                    data[rdata['eid']] = rdata

        return data

    def clearAllRemoteData(self):
        '''
        Remove all the remote estate files
        '''
        self.saltRaetKey.delete_all()

    def dumpLocalEstate(self, estate):
        '''
        Dump the key data from the local estate
        '''
        self.saltRaetKey.write_local(estate.priver.keyhex, estate.signer.keyhex)

    def dumpRemoteEstate(self, estate):
        '''
        Dump the data from the remote estate
        '''
        pass

    def dumpAllRemoteEstates(self, estates):
        '''
        Dump the data from all the remote estates
        '''
        for estate in estates:
            self.dumpRemoteEstate(estate)


    def loadRemoteEstate(self, estate, status='accepted'):
        '''
        Load and Return the data from the remote estate file
        Override this in sub class to change uid
        '''
        mid = estate.name
        keydata = self.saltRaetKey.read_remote(mid, status)
        if not keydata:
            return None

        data = odict()
        data['eid'] = keydata['device_id']
        data['name'] = keydata['minion_id']
        data['acceptance'] = raeting.ACCEPTANCES[status]
        data['verhex'] = keydata['verify']
        data['pubhex'] = keydata['pub']

        return data

    def clearRemoteEstate(self, estate):
        '''
        Clear the remote estate file
        Override this in sub class to change uid
        '''
        mid = estate.eid
        self.saltRaetKey.delete_key(mid)

    def statusRemoteEstate(self, estate, verhex, pubhex, main=True):
        '''
        Evaluate acceptance status of estate per its keys
        persist key data differentially based on status
        '''
        status = raeting.ACCEPTANCES[self.saltRaetKey.status(estate.name,
                                                             estate.eid,
                                                             pubhex,
                                                             verhex)]

        if status != raeting.acceptances.rejected:
            if (verhex and verhex != estate.verfer.keyhex):
                estate.verfer = nacling.Verifier(verhex)
            if (pubhex and pubhex != estate.pubber.keyhex):
                estate.pubber = nacling.Publican(pubhex)
        estate.acceptance = status
        return status

    def rejectRemoteEstate(self, estate):
        '''
        Set acceptance status to rejected
        '''
        estate.acceptance = raeting.acceptances.rejected
        mid = estate.name
        self.saltRaetKey.reject(match=mid, include_accepted=True)

    def acceptRemoteEstate(self, estate):
        '''
        Set acceptance status to accepted
        '''
        estate.acceptance = raeting.acceptances.accepted
        mid = estate.name
        self.saltRaetKey.accept(match=mid, include_rejected=True)


def clearAllRoadSafe(dirpath, opts):
    '''
    Convenience function to clear all road and safe keep data in dirpath
    '''
    road = keeping.RoadKeep(dirpath=dirpath)
    road.clearLocalData()
    road.clearAllRemoteData()
    safe = SaltSafe(opts=opts)
    safe.clearLocalData()
    safe.clearAllRemoteData()
