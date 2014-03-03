# -*- coding: utf-8 -*-
'''
keeping.py raet protocol keep classes
'''
# pylint: skip-file
# pylint: disable=W0611

# Import python libs
import os
from collections import deque

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
from . import estating
from . import transacting

from ioflo.base.consoling import getConsole
console = getConsole()


class Keep(object):
    '''
    RAET protocol base class for estate data persistence
    '''
    def __init__(self, dirpath='', prefix='estate', ext='json', **kwa):
        '''
        Setup Keep instance
        Create directories for saving associated estate data files
            keep/
                local/
                remote/
        '''
        if not dirpath:
            dirpath = "/tmp/raet/keep"
        self.dirpath = os.path.abspath(dirpath)
        if not os.path.exists(self.dirpath):
            os.makedirs(self.dirpath)

        self.localdirpath = os.path.join(self.dirpath, 'local')
        if not os.path.exists(self.localdirpath):
            os.makedirs(self.localdirpath)

        self.remotedirpath = os.path.join(self.dirpath, 'remote')
        if not os.path.exists(self.remotedirpath):
            os.makedirs(self.remotedirpath)

        self.prefix = prefix
        self.ext = ext
        self.localfilepath = os.path.join(self.localdirpath,
                "{0}.{1}".format(self.prefix, self.ext))

    @staticmethod
    def dump(data, filepath):
        '''
        Write data as json to filepath
        '''
        if ' ' in filepath:
            raise raeting.KeepError("Invalid filepath '{0}' contains space")

        with aiding.ocfn(filepath, "w+") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

    @staticmethod
    def load(filepath):
        '''
        Return data read from filepath as converted json
        Otherwise return None
        '''
        with aiding.ocfn(filepath) as f:
            try:
                it = json.load(f, object_pairs_hook=odict)
            except EOFError:
                return None
            except ValueError:
                return None
            return it
        return None

    def dumpLocalData(self, data):
        '''
        Dump the data from the local estate
        '''
        self.dump(data, self.localfilepath)

    def loadLocalData(self):
        '''
        Load and Return the data from the local estate
        '''
        if not os.path.exists(self.localfilepath):
            return None
        return (self.load(self.localfilepath))

    def removeLocalData(self):
        '''
        Load and Return the data from the local estate
        '''
        if os.path.exists(self.localfilepath):
            os.remove(self.localfilepath)

    def dumpRemoteData(self, data, uid):
        '''
        Dump the data from the remote estate to file named with uid
        '''
        filepath = os.path.join(self.remotedirpath,
                "{0}.{1}.{2}".format(self.prefix, uid, self.ext))

        self.dump(data, filepath)

    def dumpAllRemoteData(self, datadict):
        '''
        Dump the data for each remote estate data in the datadict keyed by uid
        '''
        for uid, data in datadict.items():
            self.dumpRemoteData(data, uid)

    def loadRemoteData(self, uid):
        '''
        Load and Return the data from the remote estate file named with uid
        '''
        filepath = os.path.join(self.remotedirpath,
                        "{0}.{1}.{2}".format(self.prefix, uid, self.ext))
        if not os.path.exists(filepath):
            return None
        return (self.load(filepath))

    def removeRemoteData(self, uid):
        '''
        Load and Return the data from the remote estate file named with uid
        '''
        filepath = os.path.join(self.remotedirpath,
                        "{0}.{1}.{2}".format(self.prefix, uid, self.ext))
        if os.path.exists(filepath):
            os.remove(filepath)

    def loadAllRemoteData(self):
        '''
        Load and Return the data from the all the remote estate files
        '''
        data = odict()
        for filename in os.listdir(self.remotedirpath):
            root, ext = os.path.splitext(filename)
            if ext != '.json' or not root.startswith(self.prefix):
                continue
            prefix, sep, uid = root.partition('.')
            if not uid or prefix != self.prefix:
                continue
            filepath = os.path.join(self.remotedirpath, filename)
            data[uid] = self.load(filepath)
        return data

    def removeAllRemoteData(self):
        '''
        Remove all the remote estate files
        '''
        for filename in os.listdir(self.remotedirpath):
            root, ext = os.path.splitext(filename)
            if ext != '.json' or not root.startswith(self.prefix):
                continue
            prefix, eid = os.path.splitext(root)
            eid = eid.lstrip('.')
            if not eid:
                continue
            filepath = os.path.join(self.remotedirpath, filename)
            if os.path.exists(filepath):
                os.remove(filepath)


    def dumpAllRemoteEstates(self, estates):
        '''
        Dump the data from the remote estate
        '''
        for estate in estates:
            self.dumpRemoteEstate(estate)

    def dumpLocalEstate(self, estate):
        '''
        Dump the key data from the local estate
        Override this in sub class to change data
        '''
        data = odict(
                eid=estate.eid,
                name=estate.name,)

        self.dumpLocalData(data)

    def dumpRemoteEstate(self, estate):
        '''
        Dump the data from the remote estate
        Override this in sub class to change data and uid
        '''
        uid = estate.eid
        data = odict(
                eid=estate.eid,
                name=estate.name,)

        self.dumpRemoteData(data, uid)

    def loadRemoteEstate(self, estate):
        '''
        Load and Return the data from the remote estate file
        Override this in sub class to change uid
        '''
        uid = estate.eid
        return (self.loadRemoteData(uid))

    def removeRemoteEstate(self, estate):
        '''
        Load and Return the data from the remote estate file
        Override this in sub class to change uid
        '''
        uid = estate.eid
        self.removeRemoteData(uid)

class RoadKeep(Keep):
    '''
    RAET protocol estate road (channel) data persistence
    '''
    def __init__(self, prefix='estate', **kwa):
        '''
        Setup RoadKeep instance
        '''
        super(RoadKeep, self).__init__(prefix=prefix, **kwa)

    def dumpLocalEstate(self, estate):
        '''
        Dump the data from the local estate
        '''
        data = odict([
                ('eid', estate.eid),
                ('name', estate.name),
                ('host', estate.host),
                ('port', estate.port),
                ('sid', estate.sid)
                ])

        self.dumpLocalData(data)

    def dumpRemoteEstate(self, estate):
        '''
        Dump the data from the remote estate
        '''
        uid = estate.eid
        data = odict([
                ('eid', estate.eid),
                ('name', estate.name),
                ('host', estate.host),
                ('port', estate.port),
                ('sid', estate.sid),
                ('rsid', estate.rsid),
                ])

        self.dumpRemoteData(data, uid)

class SafeKeep(Keep):
    '''
    RAET protocol estate safe (key) data persistence and status
    '''
    def __init__(self, prefix='key', **kwa):
        '''
        Setup SafeKeep instance
        '''
        super(SafeKeep, self).__init__(prefix=prefix, **kwa)

        self.pendeddirpath = os.path.join(self.remotedirpath, 'pended')
        if not os.path.exists(self.pendeddirpath):
            os.makedirs(self.pendeddirpath)

        self.rejecteddirpath = os.path.join(self.remotedirpath, 'rejected')
        if not os.path.exists(self.rejecteddirpath):
            os.makedirs(self.rejecteddirpath)


    def dumpLocalEstate(self, estate):
        '''
        Dump the key data from the local estate
        '''
        data = odict([
                ('eid', estate.eid),
                ('name', estate.name),
                ('sighex', estate.signer.keyhex),
                ('prihex', estate.priver.keyhex),
                ])

        self.dumpLocalData(data)

    def dumpRemoteEstate(self, estate):
        '''
        Dump the data from the remote estate
        '''
        uid = estate.name
        data = odict([
                ('eid', estate.eid),
                ('name', estate.name),
                ('verhex', estate.verfer.keyhex),
                ('pubhex', estate.pubber.keyhex),
                ])

        self.dumpRemoteData(data, uid)

    def loadRemoteEstate(self, estate):
        '''
        Load and Return the data from the remote estate file
        Override this in sub class to change uid
        '''
        uid = estate.name
        return (self.loadRemoteData(uid))

    def removeRemoteEstate(self, estate):
        '''
        Load and Return the data from the remote estate file
        Override this in sub class to change uid
        '''
        uid = estate.name
        self.removeRemoteData(uid)

    def remoteAcceptStatus(self, estate):
        '''
        Evaluate acceptance status of estate per its keys
        persist key data differentially based on status
        '''
        return (raeting.acceptance.accepted)
