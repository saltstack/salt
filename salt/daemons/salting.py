# -*- coding: utf-8 -*-
'''
salting.py module of salt specific interfaces to raet

'''
# pylint: skip-file
# pylint: disable=W0611

# Import Python libs
import os

# Import ioflo libs
from ioflo.base.odicting import odict

from ioflo.base.consoling import getConsole
console = getConsole()

from raet import raeting, nacling
from raet.road.keeping import RoadKeep

from salt.key import RaetKey


class SaltKeep(RoadKeep):
    '''
    RAET protocol estate on road data persistence for a given estate
    road specific data

    road/
        keep/
            stackname/
                local/
                    estate.ext
                remote/
                    estate.uid.ext
                    estate.uid.ext
    '''
    LocalFields = ['uid', 'name', 'ha', 'main', 'sid', 'neid', 'sighex', 'prihex', 'auto']
    LocalDumpFields = ['uid', 'name', 'ha', 'main', 'sid', 'neid']
    RemoteFields = ['uid', 'name', 'ha', 'sid', 'joined', 'acceptance', 'verhex', 'pubhex']
    RemoteDumpFields = ['uid', 'name', 'ha', 'sid', 'joined']

    Auto = False #auto accept

    def __init__(self, opts, basedirpath='', auto=None, **kwa):
        '''
        Setup RoadKeep instance
        '''
        basedirpath = basedirpath or os.path.join(opts['cache_dir'], 'raet')
        auto = auto if auto is not None else opts['auto_accept']
        super(SaltKeep, self).__init__(basedirpath=basedirpath, auto=auto, **kwa)
        self.saltRaetKey = RaetKey(opts)

    def loadLocalData(self):
        '''
        Load and Return the data from the local estate
        '''

        data = super(SaltKeep, self).loadLocalData()
        if not data:
            return None
        srkdata = self.saltRaetKey.read_local()
        if not srkdata:
            srkdata = dict(sign=None, priv=None)
        data.update(sighex=srkdata['sign'], prihex=srkdata['priv'], auto=self.auto)
        return data

    def dumpLocal(self, local):
        '''
        Dump local estate
        '''
        data = odict([
                        ('uid', local.uid),
                        ('name', local.name),
                        ('ha', local.ha),
                        ('main', local.main),
                        ('sid', local.sid),
                        ('neid', local.neid),
                    ])
        if self.verifyLocalData(data, localFields = self.LocalDumpFields):
            self.dumpLocalData(data)

        self.saltRaetKey.write_local(local.priver.keyhex, local.signer.keyhex)

    def dumpRemote(self, remote):
        '''
        Dump remote estate
        '''
        data = odict([
                        ('uid', remote.uid),
                        ('name', remote.name),
                        ('ha', remote.ha),
                        ('sid', remote.sid),
                        ('joined', remote.joined),
                    ])
        if self.verifyRemoteData(data, remoteFields =self.RemoteDumpFields):
            self.dumpRemoteData(data, remote.uid)

        self.saltRaetKey.status(remote.name,
                                remote.uid,
                                remote.pubber.keyhex,
                                remote.verfer.keyhex)

    def loadRemote(self, remote):
        '''
        Load and Return the data from the remote estate file
        Override this in sub class to change uid
        '''
        data = super(SaltKeep, self).loadRemote(remote)
        if not data:
            return None

        mid = remote.name
        statae = raeting.ACCEPTANCES.keys()
        for status in statae:
            keydata = self.saltRaetKey.read_remote(mid, status)
            if keydata:
                break

        if not keydata:
            return None

        data.update(acceptance=raeting.ACCEPTANCES[status],
                    verhex=keydata['verify'],
                    pubhex=keydata['pub'])

        return data

    def loadAllRemoteData(self):
        '''
        Load and Return the data from the all the remote estate files
        '''
        data = super(SaltKeep, self).loadAllRemoteData()

        for status, mids in self.saltRaetKey.list_keys().items():
            for mid in mids:
                keydata = self.saltRaetKey.read_remote(mid, status)
                if keydata:
                    uid = str(keydata['device_id'])
                    if uid in data:
                        data[uid].update(acceptance=raeting.ACCEPTANCES[status],
                                         verhex=keydata['verify'],
                                         pubhex=keydata['pub'])
        return data

    def clearAllRemoteData(self):
        '''
        Remove all the remote estate files
        '''
        super(SaltKeep, self).clearAllRemoteData()
        self.saltRaetKey.delete_all()

    def replaceRemote(self, remote, old):
        '''
        Replace the safe keep key file at old name given remote.name has changed
        Assumes name uniqueness already taken care of
        '''
        new = remote.name
        if new != old:
            self.dumpRemote(remote) #will be pending by default unless autoaccept
            # manually fix up acceptance if not pending
            if remote.acceptance == raeting.acceptances.accepted:
                self.acceptRemote(remote)
            elif remote.acceptance == raeting.acceptances.rejected:
                self.rejectRemote(remote)

            self.saltRaetKey.delete_key(old) #now delete old key file

    def statusRemote(self, remote, verhex, pubhex, main=True):
        '''
        Evaluate acceptance status of remote estate per its keys
        persist key data differentially based on status
        '''
        status = raeting.ACCEPTANCES[self.saltRaetKey.status(remote.name,
                                                             remote.eid,
                                                             pubhex,
                                                             verhex)]

        if status != raeting.acceptances.rejected:
            if (verhex and verhex != remote.verfer.keyhex):
                remote.verfer = nacling.Verifier(verhex)
            if (pubhex and pubhex != remote.pubber.keyhex):
                remote.pubber = nacling.Publican(pubhex)
            remote.acceptance = status

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

def clearAllKeep(dirpath):
    '''
    Convenience function to clear all road keep data in dirpath
    '''
    road = RoadKeep(dirpath=dirpath)
    road.clearLocalData()
    road.clearAllRemoteData()

