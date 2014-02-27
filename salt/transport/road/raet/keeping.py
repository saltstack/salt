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
from . import devicing
from . import transacting

from ioflo.base.consoling import getConsole
console = getConsole()


class Keep(object):
    '''
    RAET protocol base class for device data persistence
    '''
    def __init__(self, dirpath='', prefix='device', ext='json', **kwa):
        '''
        Setup Keep instance
        Create directories for saving associated device data files
            keep/
                local/
                remote/
        '''
        if not dirpath:
            dirpath = "/tmp/raet/keep"
        self.dirpath = os.path.abspath(dirpath)
        if not os.path.exists(self.dirpath):
            os.mkdirs(self.dirpath)

        self.localdirpath = os.path.join(self.dirpath, 'local')
        if not os.path.exists(self.localdirpath):
            os.mkdirs(self.localdirpath)

        self.remotedirpath = os.path.join(self.dirpath, 'remote')
        if not os.path.exists(self.remotedirpath):
            os.mkdirs(self.remotedirpath)

        self.prefix = prefix
        self.ext = ext
        self.localfilepath = os.path.join(self.localdirpath,
                "{0}.{1}".format(self.prefix, self.ext))

    @staticmethod
    def dump(data, filepath):
        '''
        Write data as json to filepath
        '''
        with ocfn(filepath, "w+") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

    @staticmethod
    def load(filepath):
        '''
        Return data read from filepath as converted json
        Otherwise return None
        '''
        with ocfn(filepath) as f:
            try:
                it = json.load(f, object_pairs_hook=odict())
            except EOFError:
                return None
            except ValueError:
                return None
            return it
        return None

    def dumpLocalData(self, data):
        '''
        Dump the data from the local device
        '''
        self.dump(data, self.localfilepath)

    def loadLocalData(self):
        '''
        Load and Return the data from the local device
        '''
        if not os.path.exists(self.localfilepath):
            return None
        return (self.load(self.localfilepath))

    def removeLocalData(self):
        '''
        Load and Return the data from the local device
        '''
        if os.path.exists(self.localfilepath):
            os.remove(self.localfilepath)

    def dumpRemoteData(self, data, did):
        '''
        Dump the data from the remote device with did
        '''
        filepath = os.path.join(self.remotedirpath,
                "{0}.{1}.{2}".format(self.prefix, did, self.ext))

        self.dump(data, filepath)

    def dumpAllRemoteData(self, datadict):
        '''
        Dump the data for each remote device data in the datadict keyed by did
        '''
        for did, data in datadict.items():
            self.dumpRemoteData(data, did)

    def loadRemoteData(self, did):
        '''
        Load and Return the data from the remote device file with did
        '''
        filepath = os.path.join(self.remotedirpath,
                        "{0}.{1}.{2}".format(self.prefix, did, self.ext))
        if not os.path.exists(filepath):
            return None
        return (self.load(filepath))

    def removeRemoteData(self, did):
        '''
        Load and Return the data from the remote device file with did
        '''
        filepath = os.path.join(self.remotedirpath,
                        "{0}.{1}.{2}".format(self.prefix, did, self.ext))
        if os.path.exists(filepath):
            os.remove(filepath)

    def loadAllRemoteData(self):
        '''
        Load and Return the data from the all the remote device files
        '''
        data = odict()
        for filename in os.listdir(self.remotedirpath):
            root, ext = os.path.splitext(filename)
            if ext != '.json' or not root.startswith(self.prefix):
                continue
            prefix, did = os.path.splitext(root)
            did = did.lstrip('.')
            if not did:
                continue
            filepath = os.path.join(self.remotedirpath, filename)
            data['did'] = self.load(filepath)
        return data

    def removeAllRemoteData(self):
        '''
        Remove all the remote device files
        '''
        for filename in os.listdir(self.remotedirpath):
            root, ext = os.path.splitext(filename)
            if ext != '.json' or not root.startswith(self.prefix):
                continue
            prefix, did = os.path.splitext(root)
            did = did.lstrip('.')
            if not did:
                continue
            filepath = os.path.join(self.remotedirpath, filename)
            if os.path.exists(filepath):
                os.remove(filepath)

    def dumpLocalDevice(self, device):
        '''
        Dump the key data from the local device
        Override this in sub class to change data
        '''
        data = odict(
                did=device.did,
                name=device.name,)

        self.dumpLocalData(data)

    def dumpRemoteDevice(self, device):
        '''
        Dump the data from the remote device
        Override this in sub class to change data
        '''
        data = odict(
                did=device.did,
                name=device.name,)

        self.dumpRemoteData(data, device.did)

    def dumpAllRemoteDevices(self, devices):
        '''
        Dump the data from the remote device
        '''
        for device in devices:
            self.dumpRemoteDevice(device)

    def loadRemoteDevice(self, device):
        '''
        Load and Return the data from the remote device file
        '''
        return (self.loadRemoteData(device.did))

    def removeRemoteDevice(self, device):
        '''
        Load and Return the data from the remote device file with did
        '''
        self.removeRemoteData(device.did)

class ChannelKeep(Keep):
    '''
    RAET protocol device channel data persistence
    '''
    def __init__(self, prefixe='device', **kwa):
        '''
        Setup ChannelKeep instance
        '''
        super(ChannelKeep, self).__init__(prefix=prefix, **kwa)

    def dumpLocalDevice(self, device):
        '''
        Dump the data from the local device
        '''
        data = odict(
                did=device.did,
                name=device.name,
                host=device.host,
                port=device.port,
                sid=device.sid)

        self.dumpLocalData(data)

    def dumpRemoteDevice(self, device):
        '''
        Dump the data from the remote device
        '''
        data = odict(
                did=device.did,
                name=device.name,
                host=device.host,
                port=device.port,
                sid=device.sid,
                rsid=device.rsid, )

        self.dumpRemoteData(data, device.did)

class KeyKeep(Keep):
    '''
    RAET protocol device key data persistence and status
    '''
    def __init__(self, prefix='key', **kwa):
        '''
        Setup KeyKeep instance
        '''
        super(KeyKeep, self).__init__(prefix=prefix, **kwa)

        self.pendeddirpath = os.path.join(self.remotedirpath, 'pended')
        if not os.path.exists(self.pendeddirpath):
            os.mkdirs(self.pendeddirpath)

        self.rejecteddirpath = os.path.join(self.remotedirpath, 'rejected')
        if not os.path.exists(self.rejecteddirpath):
            os.mkdirs(self.rejecteddirpath)


    def dumpLocalDevice(self, device):
        '''
        Dump the key data from the local device
        '''
        data = odict(
                did=device.did,
                name=device.name,
                sighex=device.signer.keyhex,
                prihex=device.priver.keyhex, )

        self.dumpLocalData(data)

    def dumpRemoteDevice(self, device):
        '''
        Dump the data from the remote device
        '''
        data = odict(
                did=device.did,
                name=device.name,
                verhex=device.verfer.keyhex,
                pubhex=device.pubber.keyhex,)

        self.dumpRemoteData(data, device.did)

    def remoteAcceptStatus(self, device):
        '''
        Evaluate acceptance status of device per its keys
        persist key data differentially based on status
        '''
        return (raeting.acceptance.accepted)
