# -*- coding: utf-8 -*-
'''
Tests to try out packeting. Potentially ephemeral

'''
# pylint: skip-file
# pylint: disable=C0103
import os

from ioflo.base.odicting import odict

from salt.transport.road.raet import (raeting, nacling, estating, keeping, stacking)


def test():
    '''
    Test keeping.
    '''


    masterDirpath = os.path.join(os.getcwd(), 'keep', 'master')
    signer = nacling.Signer()
    masterSignKeyHex = signer.keyhex
    masterVerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    masterPriKeyHex = privateer.keyhex
    masterPubKeyHex = privateer.pubhex

    m1Dirpath = os.path.join(os.getcwd(), 'keep', 'minion1')
    signer = nacling.Signer()
    m1SignKeyHex = signer.keyhex
    m1VerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    m1PriKeyHex = privateer.keyhex
    m1PubKeyHex = privateer.pubhex

    signer = nacling.Signer()
    m2SignKeyHex = signer.keyhex
    m2VerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    m2PriKeyHex = privateer.keyhex
    m2PubKeyHex = privateer.pubhex

    signer = nacling.Signer()
    m3SignKeyHex = signer.keyhex
    m3VerKeyHex = signer.verhex
    privateer = nacling.Privateer()
    m3PriKeyHex = privateer.keyhex
    m3PubKeyHex = privateer.pubhex

    keeping.clearAllRoadSafe(masterDirpath)
    keeping.clearAllRoadSafe(m1Dirpath)

    #master stack
    dirpath = os.path.join(os.getcwd(), 'keep', 'master')
    estate = estating.LocalEstate(  eid=1,
                                    name='master',
                                    sigkey=masterSignKeyHex,
                                    prikey=masterPriKeyHex,)
    stack0 = stacking.StackUdp(estate=estate, dirpath=masterDirpath)

    stack0.addRemoteEstate(estating.RemoteEstate(eid=2,
                                    ha=('127.0.0.1', 7532),
                                    verkey=m1VerKeyHex,
                                    pubkey=m1PubKeyHex,))

    stack0.addRemoteEstate(estating.RemoteEstate(eid=3,
                                    ha=('127.0.0.1', 7533),
                                    verkey=m2VerKeyHex,
                                    pubkey=m2PubKeyHex,))

    #minion stack
    dirpath = os.path.join(os.getcwd(), 'keep', 'minion1')
    estate = estating.LocalEstate(   eid=2,
                                     name='minion1',
                                     ha=("", raeting.RAET_TEST_PORT),
                                     sigkey=m1SignKeyHex,
                                     prikey=m1PriKeyHex,)
    stack1 = stacking.StackUdp(estate=estate, dirpath=m1Dirpath)


    stack1.addRemoteEstate(estating.RemoteEstate(eid=1,
                                    ha=('127.0.0.1', 7532),
                                    verkey=masterVerKeyHex,
                                    pubkey=masterPubKeyHex,))

    stack1.addRemoteEstate(estating.RemoteEstate(eid=4,
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

    stack0.serverUdp.close()
    stack1.serverUdp.close()

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
