# -*- coding: utf-8 -*-
'''
salting.py module of salt specific interfaces to raet

'''
# pylint: skip-file
# pylint: disable=W0611

# Import Python libs
import os
from collections import namedtuple, OrderedDict

# Import ioflo libs
from ioflo.base.odicting import odict

from ioflo.base.consoling import getConsole
console = getConsole()

from raet import raeting, nacling
from raet.keeping import Keep

from salt.key import RaetKey

# Python equivalent of an enum
APPL_KINDS = OrderedDict([('master', 0), ('minion', 1), ('syndic', 2), ('call', 3)])
APPL_KIND_NAMES = odict((v, k) for k, v in APPL_KINDS.iteritems())  # inverse map
ApplKind = namedtuple('ApplKind', APPL_KINDS.keys())
applKinds = ApplKind(**APPL_KINDS)


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
    LocalFields = ['name', 'uid', 'ha', 'iha', 'natted', 'fqdn', 'dyned', 'sid',
                   'puid', 'aha', 'role', 'sighex','prihex']
    LocalDumpFields = ['name', 'uid', 'ha', 'iha', 'natted', 'fqdn', 'dyned', 'sid',
                       'puid', 'aha', 'role']
    RemoteFields = ['name', 'uid', 'fuid', 'ha', 'iha', 'natted', 'fqdn', 'dyned',
                    'sid', 'main', 'kind', 'joined',
                    'role', 'acceptance', 'verhex', 'pubhex']
    RemoteDumpFields = ['name', 'uid', 'fuid', 'ha', 'iha', 'natted', 'fqdn', 'dyned',
                         'sid', 'main', 'kind', 'joined', 'role']
    Auto = raeting.autoModes.never #auto accept

    def __init__(self, opts, prefix='estate', basedirpath='',  auto=None, **kwa):
        '''
        Setup RoadKeep instance
        '''
        basedirpath = basedirpath or os.path.join(opts['cache_dir'], 'raet')
        super(SaltKeep, self).__init__(prefix=prefix, basedirpath=basedirpath, **kwa)
        self.auto = (auto if auto is not None else
                            (raeting.autoModes.always if opts['open_mode'] else
                                (raeting.autoModes.once if opts['auto_accept'] else
                                 raeting.autoModes.never)))
        self.saltRaetKey = RaetKey(opts)

    def clearAllDir(self):
        '''
        Clear all keep directories
        '''
        super(SaltKeep, self).clearAllDir()
        self.clearRoleDir()

    def clearRoleDir(self):
        '''
        Clear the Role directory
        '''
        self.saltRaetKey.delete_pki_dir()

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
        data.update([('sighex', srkdata['sign']),
                     ('prihex', srkdata['priv'])])
        return data

    def clearLocalRoleData(self):
        '''
        Clear the local file
        '''
        self.saltRaetKey.delete_local()

    def clearLocalRoleDir(self):
        '''
        Clear the Local Role directory
        '''
        self.saltRaetKey.delete_pki_dir()

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
            data.update([('acceptance', None),
                         ('verhex', None),
                         ('pubhex', None)])
        else:
            data.update(acceptance=raeting.ACCEPTANCES[status],
                        verhex=keydata['verify'],
                        pubhex=keydata['pub'])

        return data

    def loadAllRemoteData(self):
        '''
        Load and Return the data from the all the remote estate files
        '''
        keeps = super(SaltKeep, self).loadAllRemoteData()
        for name, data in keeps.items():
            keeps[name].update([('acceptance', None),
                                ('verhex', None),
                                ('pubhex', None)])

        for status, mids in self.saltRaetKey.list_keys().items():
            for mid in mids:
                keydata = self.saltRaetKey.read_remote(mid, status)
                if keydata:
                    for name, data in keeps.items():
                        if data['role'] == mid:
                            keeps[name].update(
                                    [('acceptance', raeting.ACCEPTANCES[status]),
                                     ('verhex', keydata['verify']),
                                     ('pubhex', keydata['pub'])])
        return keeps

    def clearRemoteRoleData(self, role):
        '''
        Clear data from the role data file
        '''
        self.saltRaetKey.delete_key(role) #now delete role key file

    def clearAllRemoteRoleData(self):
        '''
        Remove all the role data files
        '''
        self.saltRaetKey.delete_all()

    def clearRemoteRoleDir(self):
        '''
        Clear the Remote Role directory
        '''
        self.saltRaetKey.delete_pki_dir()

    def dumpLocal(self, local):
        '''
        Dump local estate
        '''
        data = odict([
                        ('name', local.name),
                        ('uid', local.uid),
                        ('ha', local.ha),
                        ('iha', local.iha),
                        ('natted', local.natted),
                        ('fqdn', local.fqdn),
                        ('dyned', local.dyned),
                        ('sid', local.sid),
                        ('puid', local.stack.puid),
                        ('aha', local.stack.aha),
                        ('role', local.role),
                    ])
        if self.verifyLocalData(data, localFields =self.LocalDumpFields):
            self.dumpLocalData(data)

        self.saltRaetKey.write_local(local.priver.keyhex, local.signer.keyhex)

    def dumpRemote(self, remote):
        '''
        Dump remote estate
        '''
        data = odict([
                        ('name', remote.name),
                        ('uid', remote.uid),
                        ('fuid', remote.fuid),
                        ('ha', remote.ha),
                        ('iha', remote.iha),
                        ('natted', remote.natted),
                        ('fqdn', remote.fqdn),
                        ('dyned', remote.dyned),
                        ('sid', remote.sid),
                        ('main', remote.main),
                        ('kind', remote.kind),
                        ('joined', remote.joined),
                        ('role', remote.role),
                    ])
        if self.verifyRemoteData(data, remoteFields=self.RemoteDumpFields):
            self.dumpRemoteData(data, remote.name)

        if remote.pubber.keyhex  and remote.verfer.keyhex:
            # kludge to persist the keys since no way to write
            self.saltRaetKey.status(remote.role,
                                remote.pubber.keyhex,
                                remote.verfer.keyhex)

    def statusRemote(self, remote, dump=True):
        '''
        Calls .statusRole on remote role and keys and updates remote.acceptance
        dump indicates if statusRole should update persisted values when
        appropriate.

        Returns status
        Where status is acceptance status of role and keys
        and has value from raeting.acceptances
        '''
        status = self.statusRole(role=remote.role,
                                 verhex=remote.verfer.keyhex,
                                 pubhex=remote.pubber.keyhex,
                                 dump=dump)

        remote.acceptance = status

        return status

    def statusRole(self, role, verhex, pubhex, dump=True):
        '''
        Returns status

        Where status is acceptance status of role and keys
        and has value from raeting.acceptances
        '''
        status = raeting.ACCEPTANCES[self.saltRaetKey.status(role,
                                                             pubhex,
                                                             verhex)]

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
