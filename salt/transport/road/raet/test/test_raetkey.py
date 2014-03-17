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

from salt.transport.road.raet import (raeting, nacling, estating, keeping,
                                      stacking, salting)


def test():
    '''
    Test keeping.
    '''
    pkiDirpath = os.path.join(os.getcwd(), 'keyo', 'pki')
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
        os.chmod(localFilepath, mode | stat.S_IWUSR | stat.S_IWUSR)


    cacheDirpath = os.path.join(os.getcwd(), 'salt', 'cache')
    sockDirpath = os.path.join('/tmp/raet', 'salt', 'sock')

    opts = dict(
                pki_dir=pkiDirpath,
                sock_dir=sockDirpath,
                cachedir=cacheDirpath,
                open_mode=True,
                auto_accept=True,
                )

    masterKeeper = RaetKey(opts=opts)
    print masterKeeper.all_keys()

    masterName = 'master'
    masterDirpath = os.path.join(os.getcwd(), 'keep', masterName )
    signer = nacling.Signer()
    masterSignKeyHex = signer.keyhex
    masterVerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    masterPriKeyHex = privateer.keyhex
    masterPubKeyHex = privateer.pubhex

    m1Name = 'minion1'
    m1Dirpath = os.path.join(os.getcwd(), 'keep', m1Name)
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

    local = masterKeeper.read_local()
    print local
    if not local:
        masterKeeper.write_local(masterPriKeyHex, masterSignKeyHex)
        print  masterKeeper.read_local()
    print masterKeeper.all_keys()

    print masterKeeper.status(m1Name, 2, m1PubKeyHex, m1VerKeyHex)
    print masterKeeper.status(m2Name, 3, m2PubKeyHex, m2VerKeyHex)
    print masterKeeper.all_keys()
    print masterKeeper.read_remote(m1Name)
    print masterKeeper.read_remote(m2Name)

    print masterKeeper.list_keys()
    print masterKeeper.read_all_remote()


    #master stack
    estate = estating.LocalEstate(  eid=1,
                                    name=masterName,
                                    sigkey=masterSignKeyHex,
                                    prikey=masterPriKeyHex,)
    stack0 = stacking.StackUdp(estate=estate, dirpath=masterDirpath)

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
    estate = estating.LocalEstate(   eid=2,
                                     name=m1Name,
                                     ha=("", raeting.RAET_TEST_PORT),
                                     sigkey=m1SignKeyHex,
                                     prikey=m1PriKeyHex,)
    stack1 = stacking.StackUdp(estate=estate, dirpath=m1Dirpath)


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

    stack0.clearLocal()
    stack0.clearAllRemote()
    stack1.clearLocal()
    stack1.clearAllRemote()

    stack0.dumpLocal()
    stack0.dumpAllRemote()

    stack1.dumpLocal()
    stack1.dumpAllRemote()

    print "Road {0}".format(stack0.name)
    print stack0.road.loadLocalData()
    print stack0.road.loadAllRemoteData()
    print "Safe {0}".format(stack0.name)
    print stack0.safe.loadLocalData()
    print stack0.safe.loadAllRemoteData()
    print

    print "Road {0}".format(stack1.name)
    print stack1.road.loadLocalData()
    print stack1.road.loadAllRemoteData()
    print "Safe {0}".format(stack1.name)
    print stack1.safe.loadLocalData()
    print stack1.safe.loadAllRemoteData()

    stack0.server.close()
    stack1.server.close()

    #master stack
    dirpath = os.path.join(os.getcwd(), 'keep', 'master')
    estate = estating.LocalEstate(  eid=1,
                                    name='master',
                                    sigkey=masterSignKeyHex,
                                    prikey=masterPriKeyHex,)
    stack0 = stacking.StackUdp(estate=estate, dirpath=masterDirpath)

    #minion stack
    dirpath = os.path.join(os.getcwd(), 'keep', 'minion1')
    estate = estating.LocalEstate(   eid=2,
                                     name='minion1',
                                     ha=("", raeting.RAET_TEST_PORT),
                                     sigkey=m1SignKeyHex,
                                     prikey=m1PriKeyHex,)
    stack1 = stacking.StackUdp(estate=estate, dirpath=m1Dirpath)


    estate0 = stack0.loadLocal()
    print estate0.name, estate0.eid, estate0.sid, estate0.ha, estate0.signer, estate0.priver
    estate1 = stack1.loadLocal()
    print estate1.name, estate1.eid, estate1.sid, estate1.ha, estate1.signer, estate1.priver

    stack0.clearLocal()
    stack0.clearAllRemote()
    stack1.clearLocal()
    stack1.clearAllRemote()


if __name__ == "__main__":


    test()
