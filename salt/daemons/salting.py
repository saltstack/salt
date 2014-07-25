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
from raet.keeping import Keep

from salt.key import RaetKey


class SaltKeep(Keep):
    '''
    RAET protocol estate on road data persistence for a given estate
    road specific data

    road/
        keep/
            stackname/
                local/
                    estate.ext
                remote/
                    estate.name.ext
                    estate.name.ext
    '''
    LocalFields = ['uid', 'name', 'ha', 'main', 'sid', 'neid', 'sighex', 'prihex', 'auto', 'role']
    LocalDumpFields = ['uid', 'name', 'ha', 'main', 'sid', 'neid', 'role']
    RemoteFields = ['uid', 'name', 'ha', 'sid', 'joined', 'acceptance', 'verhex', 'pubhex', 'role']
    RemoteDumpFields = ['uid', 'name', 'ha', 'sid', 'joined', 'role']

    Auto = False #auto accept

    def __init__(self, opts, prefix='estate', basedirpath='',  auto=None, **kwa):
        '''
        Setup RoadKeep instance
        '''
        basedirpath = basedirpath or os.path.join(opts['cache_dir'], 'raet')
        super(SaltKeep, self).__init__(prefix=prefix, basedirpath=basedirpath, **kwa)
        self.auto = auto if auto is not None else opts['auto_accept']
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

    def loadRemoteData(self, name):
        '''
        Load and Return the data from the remote file
        '''
        data = super(SaltKeep, self).loadRemoteData(name)
        if not data:
            return None

        mid = data['role']
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
        keeps = super(SaltKeep, self).loadAllRemoteData()

        for status, mids in self.saltRaetKey.list_keys().items():
            for mid in mids:
                keydata = self.saltRaetKey.read_remote(mid, status)
                if keydata:
                    for name, data in keeps.items():
                        if data['role'] == mid:
                            keeps[name].update(acceptance=raeting.ACCEPTANCES[status],
                                         verhex=keydata['verify'],
                                         pubhex=keydata['pub'])
        return keeps

    def clearAllRemoteData(self):
        '''
        Remove all the remote estate files
        '''
        super(SaltKeep, self).clearAllRemoteData()
        self.saltRaetKey.delete_all()

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
                        ('role', local.role),
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
                        ('role', remote.role),
                    ])
        if self.verifyRemoteData(data, remoteFields=self.RemoteDumpFields):
            self.dumpRemoteData(data, remote.name)

        self.saltRaetKey.status(remote.role,
                                remote.pubber.keyhex,
                                remote.verfer.keyhex)


    def replaceRemoteRole(self, remote, old):
        '''
        Replace the Salt RaetKey record at old role when remote.role has changed
        '''
        new = remote.role
        if new != old:
            #self.dumpRemote(remote)
            # manually fix up acceptance if not pending
            # will be pending by default unless autoaccept
            if remote.acceptance == raeting.acceptances.accepted:
                self.acceptRemote(remote)
            elif remote.acceptance == raeting.acceptances.rejected:
                self.rejectRemote(remote)

            self.saltRaetKey.delete_key(old) #now delete old key file

    def statusRemote(self, remote, verhex, pubhex, main=True, dump=True):
        '''
        Evaluate acceptance status of remote estate per its keys
        persist key data differentially based on status
        '''
        status = raeting.ACCEPTANCES[self.saltRaetKey.status(remote.role,
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
        mid = remote.role
        self.saltRaetKey.reject(match=mid, include_accepted=True)
        remote.acceptance = raeting.acceptances.rejected

    def pendRemote(self, remote):
        '''
        Set acceptance status to pending
        '''
        pass

    def acceptRemote(self, remote):
        '''
        Set acceptance status to accepted
        '''
        mid = remote.role
        self.saltRaetKey.accept(match=mid, include_rejected=True)
        remote.acceptance = raeting.acceptances.accepted

def clearAllKeep(dirpath):
    '''
    Convenience function to clear all road keep data in dirpath
    '''
    road = RoadKeep(dirpath=dirpath)
    road.clearLocalData()
    road.clearAllRemoteData()

