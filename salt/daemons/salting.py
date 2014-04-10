# -*- coding: utf-8 -*-
'''
salting.py module of salt specific interfaces to raet

'''
# pylint: skip-file
# pylint: disable=W0611

# Import Python libs

# Import ioflo libs
from ioflo.base.odicting import odict

from ioflo.base.consoling import getConsole
console = getConsole()

from raet import raeting, nacling, keeping
from raet.road.keeping import RoadKeep

from salt.key import RaetKey

class SaltSafe(object):
    '''
    Interface between Salt Key management and RAET keep key management
    '''
    Auto = False #auto accept

    def __init__(self, opts=None, **kwa):
        '''
        Setup SaltSafe instance
        '''
        if opts is None:
            opts = {}
        self.saltRaetKey = RaetKey(opts)
        
    def dumpLocalData(self, data):
        '''
        Dump the key data from the local estate
        '''      
        self.saltRaetKey.write_local(data.prihex, data.sighex)    

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

    def dumpRemote(self, estate):
        '''
        Dump the data from the remote estate
        '''
        pass

    def loadRemote(self, remote):
        '''
        Load and Return the data from the remote estate file
        Override this in sub class to change uid
        '''
        status='accepted'
        
        mid = remote.name
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

    def clearRemote(self, remote):
        '''
        Clear the remote estate file
        Override this in sub class to change uid
        '''
        mid = remote.eid
        self.saltRaetKey.delete_key(mid)

    def statusRemote(self, estate, verhex, pubhex, main=True):
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

    def rejectRemote(self, remote):
        '''
        Set acceptance status to rejected
        '''
        remote.acceptance = raeting.acceptances.rejected
        mid = remote.name
        self.saltRaetKey.reject(match=mid, include_accepted=True)
        
    def pendRemote(self, remote):
         '''
         Set acceptance status to pending
         '''
         pass    

    def acceptRemote(self, remote):
        '''
        Set acceptance status to accepted
        '''
        remote.acceptance = raeting.acceptances.accepted
        mid = remote.name
        self.saltRaetKey.accept(match=mid, include_rejected=True)


def clearAllRoadSafe(dirpath, opts):
    '''
    Convenience function to clear all road and safe keep data in dirpath
    '''
    road = RoadKeep(dirpath=dirpath)
    road.clearLocalData()
    road.clearAllRemoteData()
    safe = SaltSafe(opts=opts)
    safe.clearLocalData()
    safe.clearAllRemoteData()
