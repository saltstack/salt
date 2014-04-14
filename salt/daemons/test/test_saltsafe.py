# -*- coding: utf-8 -*-
'''
Tests to try out salt key.RaetKey Potentially ephemeral

'''
# pylint: skip-file
# pylint: disable=C0103
import os
import stat

from ioflo.base.odicting import odict

from salt.key import RaetKey

from salt.daemons import salting
from raet import raeting, nacling
from raet.road import keeping, estating, stacking


def test():
    '''
    Test keeping.
    '''
    pkiDirpath = os.path.join('/tmp', 'raet', 'keyo', 'master', 'pki')
    if not os.path.exists(pkiDirpath):
            os.makedirs(pkiDirpath)

    acceptedDirpath = os.path.join(pkiDirpath, 'accepted')
    if not os.path.exists(acceptedDirpath):
        os.makedirs(acceptedDirpath)

    pendingDirpath = os.path.join(pkiDirpath, 'pending')
    if not os.path.exists(pendingDirpath):
        os.makedirs(pendingDirpath)

    rejectedDirpath = os.path.join(pkiDirpath, 'rejected')
    if not os.path.exists(rejectedDirpath):
        os.makedirs(rejectedDirpath)

    localFilepath = os.path.join(pkiDirpath, 'local.key')
    if os.path.exists(localFilepath):
        mode = os.stat(localFilepath).st_mode
        print mode
        os.chmod(localFilepath, mode | stat.S_IWUSR | stat.S_IRUSR)
        mode = os.stat(localFilepath).st_mode
        print mode


    cacheDirpath = os.path.join('/tmp/raet', 'cache', 'master')
    sockDirpath = os.path.join('/tmp/raet', 'sock', 'master')

    opts = dict(
                pki_dir=pkiDirpath,
                sock_dir=sockDirpath,
                cachedir=cacheDirpath,
                open_mode=True,
                auto_accept=True,
                transport='raet',
                )

    masterSafe = salting.SaltSafe(opts=opts)
    print("masterSafe local =\n{0}".format(masterSafe.loadLocalData()))
    print("masterSafe remote =\n{0}".format(masterSafe.loadAllRemoteData()))

    pkiDirpath = os.path.join('/tmp', 'raet', 'keyo', 'minion', 'pki')
    if not os.path.exists(pkiDirpath):
            os.makedirs(pkiDirpath)

    acceptedDirpath = os.path.join(pkiDirpath, 'accepted')
    if not os.path.exists(acceptedDirpath):
        os.makedirs(acceptedDirpath)

    pendingDirpath = os.path.join(pkiDirpath, 'pending')
    if not os.path.exists(pendingDirpath):
        os.makedirs(pendingDirpath)

    rejectedDirpath = os.path.join(pkiDirpath, 'rejected')
    if not os.path.exists(rejectedDirpath):
        os.makedirs(rejectedDirpath)

    localFilepath = os.path.join(pkiDirpath, 'local.key')
    if os.path.exists(localFilepath):
        mode = os.stat(localFilepath).st_mode
        print mode
        os.chmod(localFilepath, mode | stat.S_IWUSR | stat.S_IRUSR)
        mode = os.stat(localFilepath).st_mode
        print mode

    cacheDirpath = os.path.join('/tmp/raet', 'cache', 'minion')
    sockDirpath = os.path.join('/tmp/raet', 'sock', 'minion')

    opts = dict(
                pki_dir=pkiDirpath,
                sock_dir=sockDirpath,
                cachedir=cacheDirpath,
                open_mode=True,
                auto_accept=True,
                transport='raet',
                )

    minionSafe = salting.SaltSafe(opts=opts)
    print("minionSafe local =\n{0}".format(minionSafe.loadLocalData()))
    print("minionSafe remote =\n{0}".format(minionSafe.loadAllRemoteData()))

    masterName = 'master'
    masterDirpath = os.path.join('/tmp', 'raet', 'keep', masterName )
    signer = nacling.Signer()
    masterSignKeyHex = signer.keyhex
    masterVerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    masterPriKeyHex = privateer.keyhex
    masterPubKeyHex = privateer.pubhex

    m1Name = 'minion1'
    m1Dirpath = os.path.join('/tmp', 'raet', 'keep', m1Name)
    signer = nacling.Signer()
    m1SignKeyHex = signer.keyhex
    m1VerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    m1PriKeyHex = privateer.keyhex
    m1PubKeyHex = privateer.pubhex

    m2Name = 'minion2'
    signer = nacling.Signer()
    m2SignKeyHex = signer.keyhex
    m2VerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    m2PriKeyHex = privateer.keyhex
    m2PubKeyHex = privateer.pubhex

    m3Name = 'minion3'
    signer = nacling.Signer()
    m3SignKeyHex = signer.keyhex
    m3VerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    m3PriKeyHex = privateer.keyhex
    m3PubKeyHex = privateer.pubhex

    keeping.clearAllRoadSafe(masterDirpath)
    keeping.clearAllRoadSafe(m1Dirpath)

    #saltsafe = salting.SaltSafe(opts=opts)
    #print saltsafe.loadLocalData()
    #print saltsafe.loadAllRemoteData()

    #master stack
    local = estating.LocalEstate(  eid=1,
                                    name=masterName,
                                    sigkey=masterSignKeyHex,
                                    prikey=masterPriKeyHex,)
    stack0 = stacking.RoadStack(local=local,
                               dirpath=masterDirpath,
                               safe=masterSafe)

    stack0.addRemote(estating.RemoteEstate(eid=2,
                                    name=m1Name,
                                    ha=('127.0.0.1', 7532),
                                    verkey=m1VerKeyHex,
                                    pubkey=m1PubKeyHex,))

    stack0.addRemote(estating.RemoteEstate(eid=3,
                                    name=m2Name,
                                    ha=('127.0.0.1', 7533),
                                    verkey=m2VerKeyHex,
                                    pubkey=m2PubKeyHex,))

    #minion stack
    local = estating.LocalEstate(   eid=2,
                                     name=m1Name,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     sigkey=m1SignKeyHex,
                                     prikey=m1PriKeyHex,)
    stack1 = stacking.RoadStack(local=local,
                               dirpath=m1Dirpath,
                               safe=minionSafe)


    stack1.addRemote(estating.RemoteEstate(eid=1,
                                    name=masterName,
                                    ha=('127.0.0.1', 7532),
                                    verkey=masterVerKeyHex,
                                    pubkey=masterPubKeyHex,))

    stack1.addRemote(estating.RemoteEstate(eid=4,
                                    name=m3Name,
                                    ha=('127.0.0.1', 7534),
                                    verkey=m3VerKeyHex,
                                    pubkey=m3PubKeyHex,))

    #stack0.clearLocal()
    stack0.clearRemoteKeeps()
    #stack1.clearLocal()
    stack1.clearRemoteKeeps()

    stack0.dumpLocal()
    stack0.dumpRemotes()

    stack1.dumpLocal()
    stack1.dumpRemotes()

    print "Road {0}".format(stack0.name)
    print stack0.keep.loadLocalData()
    print stack0.keep.loadAllRemoteData()
    print "Safe {0}".format(stack0.name)
    print stack0.safe.loadLocalData()
    print stack0.safe.loadAllRemoteData()
    print

    print "Road {0}".format(stack1.name)
    print stack1.keep.loadLocalData()
    print stack1.keep.loadAllRemoteData()
    print "Safe {0}".format(stack1.name)
    print stack1.safe.loadLocalData()
    print stack1.safe.loadAllRemoteData()

    stack0.server.close()
    stack1.server.close()

    #master stack
    dirpath = os.path.join('/tmp/raet', 'keep', 'master')
    local = estating.LocalEstate(  eid=1,
                                    name='master',
                                    sigkey=masterSignKeyHex,
                                    prikey=masterPriKeyHex,)
    stack0 = stacking.RoadStack(local=local,
                               dirpath=masterDirpath,
                               safe=masterSafe)

    #minion stack
    dirpath = os.path.join('/tmp/raet', 'keep', 'minion1')
    local = estating.LocalEstate(   eid=2,
                                     name='minion1',
                                     ha=("", raeting.RAET_TEST_PORT),
                                     sigkey=m1SignKeyHex,
                                     prikey=m1PriKeyHex,)
    stack1 = stacking.RoadStack(local=local,
                               dirpath=m1Dirpath,
                               safe=minionSafe)


    stack0.loadLocal()
    print stack0.local.name, stack0.local.eid, stack0.local.sid, stack0.local.ha, stack0.local.signer, stack0.local.priver
    stack1.loadLocal()
    print stack1.local.name, stack1.local.eid, stack1.local.sid, stack1.local.ha, stack1.local.signer, stack1.local.priver

    stack0.clearLocal()
    stack0.clearRemoteKeeps()
    stack1.clearLocal()
    stack1.clearRemoteKeeps()


if __name__ == "__main__":


    test()
